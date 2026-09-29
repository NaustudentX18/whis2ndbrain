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

                def js(script: str):
                    return _json_request(endpoint + "/execute/sync", "POST", {"script": script, "args": []})["value"]

                # Login through the real form (BP1 item 2): the raw owner
                # token is no longer accepted as a cookie value.
                _json_request(endpoint + "/url", "POST", {"url": origin + "/"})
                try:
                    _json_request(endpoint + "/execute/sync", "POST", {
                        "script": (
                            "const f = document.querySelector('input[name=token]');"
                            "f.value = arguments[0]; f.form.submit();"
                        ),
                        "args": [token],
                    })
                except OSError:
                    # form.submit() navigates away and can destroy the
                    # execution context mid-call; the poll below is the
                    # real signal, not this fire-and-forget call.
                    pass
                for _ in range(30):
                    if js("return !document.querySelector('input[name=token]')"):
                        break
                    time.sleep(0.1)
                _json_request(endpoint + "/url", "POST", {"url": origin + "/pwa"})

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


    def test_pwa_trash_and_retry_flow(self):
        """B2: the shell covers the item-4 surface - tombstone, trash view,
        restore, retry affordance - not just the single-note smoke."""
        with tempfile.TemporaryDirectory(prefix="whis-browser-test-") as temp:
            store = Store(Path(temp) / "store")
            store.accept("pwa-cap-1", synthetic_wav())
            store.set_transcript("pwa-cap-1", "Keep me around", source="model")
            store.accept("pwa-cap-2", synthetic_wav())
            store.mark_not_transcribed("pwa-cap-2")
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
                _json_request(endpoint + "/url", "POST", {"url": origin + "/"})

                def js(script: str):
                    return _json_request(endpoint + "/execute/sync", "POST", {"script": script, "args": []})["value"]

                try:
                    _json_request(endpoint + "/execute/sync", "POST", {
                        "script": (
                            "const f = document.querySelector('input[name=token]');"
                            "f.value = arguments[0]; f.form.submit();"
                        ),
                        "args": [token],
                    })
                except OSError:
                    # form.submit() navigates away and can destroy the
                    # execution context mid-call; the poll below is the
                    # real signal, not this fire-and-forget call.
                    pass
                for _ in range(30):
                    try:
                        if js("return !document.querySelector('input[name=token]')"):
                            break
                    except OSError:
                        pass  # navigation in flight
                    time.sleep(0.1)
                _json_request(endpoint + "/url", "POST", {"url": origin + "/pwa"})

                def cards():
                    try:
                        return js("return document.querySelectorAll('.note-card').length")
                    except OSError:
                        return -1  # navigation in flight; retry on next poll

                def wait_for(predicate, timeout=30):
                    for _ in range(timeout):
                        if predicate():
                            return True
                        time.sleep(0.1)
                    return False

                self.assertTrue(wait_for(lambda: cards() == 2), "both notes render")
                # the not_transcribed note offers Retry; the healthy one does not
                self.assertEqual(
                    js('return document.querySelectorAll(\'.note-card[data-id="pwa-cap-2"] .retry-btn\').length'), 1
                )
                self.assertEqual(js("return document.querySelectorAll('.retry-btn').length"), 1)
                # delete the healthy note -> tombstoned, hidden from the feed
                js('document.querySelector(\'.note-card[data-id="pwa-cap-1"] .delete-btn\').click()')
                self.assertTrue(wait_for(lambda: cards() == 1), "deleted note leaves the feed")
                self.assertIsNotNone(store.get_note("pwa-cap-1").deleted_at)
                # trash view shows it with a Restore affordance
                js("document.getElementById('trashToggle').click()")
                self.assertTrue(wait_for(lambda: cards() == 2), "trash view lists the tombstone")
                self.assertEqual(
                    js('return document.querySelectorAll(\'.note-card[data-id="pwa-cap-1"] .restore-btn\').length'), 1
                )
                js('document.querySelector(\'.note-card[data-id="pwa-cap-1"] .restore-btn\').click()')
                self.assertTrue(wait_for(lambda: store.get_note("pwa-cap-1").deleted_at is None), "restore clears the tombstone")
                # back on the normal view both notes are listed again
                js("document.getElementById('trashToggle').click()")
                self.assertTrue(wait_for(lambda: cards() == 2))
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
