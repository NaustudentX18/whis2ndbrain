"""Optional local Chromium smoke for the disposable review page.

Run explicitly with ``python -m unittest tests.e2e.test_browser_review``.
Requires chromedriver and Chromium; never uses the live service or vault.
"""

from __future__ import annotations

import json
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

from server.pass1 import Store
from server.review import create_handler
from tests.integration.test_http_review import synthetic_wav


def _json_request(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data is not None else {},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.load(response)


@unittest.skipUnless(shutil.which("chromedriver") and shutil.which("chromium"), "Chromium driver unavailable")
class BrowserReviewTests(unittest.TestCase):
    def test_mobile_inbox_correction_and_download_link(self):
        with tempfile.TemporaryDirectory(prefix="whis-browser-test-") as temp:
            store = Store(Path(temp) / "store")
            cid = "browser-capture-001"
            store.accept(cid, synthetic_wav())
            store.set_transcript(cid, "Original synthetic transcript", source="model")
            token = "synthetic-browser-token"
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), create_handler(store, token, runner=None))
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            driver = None
            session_id = None
            try:
                with socket.socket() as probe:
                    probe.bind(("127.0.0.1", 0))
                    driver_port = probe.getsockname()[1]
                driver = subprocess.Popen(
                    ["chromedriver", f"--port={driver_port}", "--allowed-ips=127.0.0.1"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                driver_url = f"http://127.0.0.1:{driver_port}"
                for _ in range(40):
                    try:
                        _json_request(driver_url + "/status")
                        break
                    except (OSError, urllib.error.URLError):
                        time.sleep(0.1)
                else:
                    self.fail("chromedriver did not start")
                created = _json_request(driver_url + "/session", "POST", {
                    "capabilities": {"alwaysMatch": {"browserName": "chrome", "goog:chromeOptions": {
                        "binary": shutil.which("chromium"),
                        "args": ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=390,844"],
                    }}}
                })
                session_id = created["value"]["sessionId"]
                endpoint = f"{driver_url}/session/{session_id}"
                origin = f"http://127.0.0.1:{httpd.server_address[1]}"
                _json_request(endpoint + "/url", "POST", {"url": origin + "/api/v1/health/live"})
                _json_request(endpoint + "/cookie", "POST", {"cookie": {
                    "name": "whis_session", "value": token, "path": "/", "httpOnly": True,
                }})
                _json_request(endpoint + "/url", "POST", {"url": origin + "/pwa"})

                def js(script: str):
                    return _json_request(endpoint + "/execute/sync", "POST", {"script": script, "args": []})["value"]

                for _ in range(30):
                    if js("return document.querySelectorAll('.note-card').length") == 1:
                        break
                    time.sleep(0.1)
                self.assertEqual(js("return document.querySelectorAll('.note-card').length"), 1)
                self.assertIn("Original synthetic transcript", js("return document.querySelector('.transcript-text').innerText"))
                self.assertTrue(js("return !!document.querySelector('audio[controls]')"))
                self.assertTrue(js("return document.querySelector('a[download]').getAttribute('download').endsWith('.md')"))
                self.assertTrue(js("return document.querySelector('a[download]').href.endsWith('/markdown')"))
                js("document.querySelector('.edit-btn').click(); document.querySelector('#editTranscriptInput').value='Corrected in Chromium'; document.querySelector('#saveModalBtn').click();")
                for _ in range(30):
                    if store.get_note(cid).transcript == "Corrected in Chromium":
                        break
                    time.sleep(0.1)
                self.assertEqual(store.get_note(cid).transcript, "Corrected in Chromium")
                self.assertEqual(store.get_note(cid).transcript_source, "owner")
            finally:
                if session_id is not None:
                    try:
                        _json_request(f"{driver_url}/session/{session_id}", "DELETE")
                    except OSError:
                        pass
                if driver is not None:
                    driver.terminate()
                    try:
                        driver.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        driver.kill()
                        driver.wait(timeout=5)
                httpd.shutdown()
                thread.join(timeout=5)
                httpd.server_close()


if __name__ == "__main__":
    unittest.main()
