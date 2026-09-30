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


    def test_accessibility_baseline_320_focus_contrast(self):
        """C3 / WB-051 prep: 320 px reflow, visible keyboard focus, AA text
        contrast, and accessible names on interactive controls.

        Automated slice of the checklist in docs/ACCESSIBILITY.md; the
        screen-reader pass, full keyboard walkthrough and 200 % OS zoom stay
        manual (headless Chromium cannot honestly prove them).
        """
        with tempfile.TemporaryDirectory(prefix="whis-browser-a11y-") as temp:
            store = Store(Path(temp) / "store")
            cid = "browser-a11y-001"
            store.accept(cid, synthetic_wav())
            store.set_transcript(cid, "Synthetic transcript for contrast checks", source="model")
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
                # 320 CSS px = WCAG 1.4.10 reflow target (and the practical
                # equivalent of 200 % zoom on a 640 px baseline viewport).
                created = _json_request(driver_url + "/session", "POST", {
                    "capabilities": {"alwaysMatch": {"browserName": "chrome", "goog:chromeOptions": {
                        "binary": shutil.which("chromium"),
                        "args": ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage", "--window-size=320,800"],
                    }}}
                })
                session_id = created["value"]["sessionId"]
                endpoint = f"{driver_url}/session/{session_id}"
                origin = f"http://127.0.0.1:{httpd.server_address[1]}"

                def js(script: str):
                    return _json_request(endpoint + "/execute/sync", "POST", {"script": script, "args": []})["value"]

                def tab_key():
                    _json_request(endpoint + "/actions", "POST", {"actions": [
                        {"type": "key", "id": "kb", "actions": [
                            {"type": "keyDown", "value": "\ue004"},
                            {"type": "keyUp", "value": "\ue004"},
                        ]}
                    ]})
                    _json_request(endpoint + "/actions", "DELETE")

                contrast_js = r"""
return (() => {
  const lum = (r, g, b) => {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const parse = s => {
    const m = (s || "").match(/rgba?\(([\d.]+),\s*([\d.]+),\s*([\d.]+)(?:,\s*([\d.]+))?\)/);
    return m ? [+m[1], +m[2], +m[3], m[4] === undefined ? 1 : +m[4]] : null;
  };
  const bgOf = el => {
    let e = el;
    while (e) {
      const c = parse(getComputedStyle(e).backgroundColor);
      if (c && c[3] > 0) return c;
      e = e.parentElement;
    }
    return [255, 255, 255, 1];  // browser default canvas when no ancestor paints a background
  };
  const out = [];
  for (const el of document.querySelectorAll(arguments[0])) {
    if (!el.textContent.trim() && !el.getAttribute('aria-label')) continue;
    const fg = parse(getComputedStyle(el).color);
    if (!fg) continue;
    const bg = bgOf(el);
    const l1 = lum(fg[0], fg[1], fg[2]), l2 = lum(bg[0], bg[1], bg[2]);
    out.push({ tag: el.tagName, text: el.textContent.trim().slice(0, 30),
               ratio: +(((Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05)).toFixed(2)) });
  }
  return out;
})();
"""
                names_js = """
return (() => {
  const bad = [];
  for (const el of document.querySelectorAll('button, a[href], input, [role=button]')) {
    const name = (el.getAttribute('aria-label') || el.getAttribute('title')
                  || el.value || el.placeholder
                  || (el.labels && el.labels.length
                      && [...el.labels].map(l => l.textContent).join(' '))
                  || el.textContent || '').toString().trim();
    if (!name) bad.push(el.tagName + (el.className ? '.' + String(el.className).split(' ')[0] : ''));
  }
  return bad;
})();
"""

                # --- Login page at 320 px ---
                _json_request(endpoint + "/url", "POST", {"url": origin + "/"})
                for _ in range(30):
                    if js("return document.readyState") == "complete":
                        break
                    time.sleep(0.1)
                self.assertLessEqual(
                    js("return document.documentElement.scrollWidth - document.documentElement.clientWidth"), 1,
                    "login page overflows horizontally at 320 px",
                )
                # Keyboard: first Tab lands on the token input with a visible
                # focus ring (2 px solid accent via :focus-visible).
                tab_key()
                focused = js("return document.activeElement.tagName + '|' + (document.activeElement.name || '')")
                self.assertTrue(focused.startswith("INPUT"), f"first Tab should focus the token input, got {focused}")
                outline = js(
                    "const s = getComputedStyle(document.activeElement);"
                    "return s.outlineStyle + '|' + s.outlineWidth;"
                )
                self.assertTrue(
                    outline.split("|")[0] not in ("none", "") and float(outline.split("|")[1].replace("px", "")) >= 1,
                    f"focused element has no visible outline ({outline})",
                )
                for row in js(contrast_js.replace("arguments[0]", "'h1, h2, label, button, a[href]'")):
                    self.assertGreaterEqual(
                        row["ratio"], 4.5,
                        f"contrast {row['ratio']}:1 < AA for <{row['tag']}> {row['text']!r} on the login page",
                    )
                self.assertEqual(js(names_js), [], "login page has unnamed interactive controls")

                # --- Review shell at 320 px after a real form login ---
                _json_request(endpoint + "/execute/sync", "POST", {
                    "script": (
                        "const f = document.querySelector('input[name=token]');"
                        "f.value = arguments[0]; f.form.submit();"
                    ),
                    "args": [token],
                })
                for _ in range(30):
                    if js("return !document.querySelector('input[name=token]')"):
                        break
                    time.sleep(0.1)
                _json_request(endpoint + "/url", "POST", {"url": origin + "/pwa"})
                for _ in range(30):
                    if js("return document.querySelectorAll('.note-card').length") == 1:
                        break
                    time.sleep(0.1)
                self.assertLessEqual(
                    js("return document.documentElement.scrollWidth - document.documentElement.clientWidth"), 1,
                    "review shell overflows horizontally at 320 px",
                )
                for row in js(contrast_js.replace("arguments[0]", "'h1, h2, .transcript-text, .btn, .filter-btn, a[href]'")):
                    self.assertGreaterEqual(
                        row["ratio"], 4.5,
                        f"contrast {row['ratio']}:1 < AA for <{row['tag']}> {row['text']!r} in the shell",
                    )
                self.assertEqual(js(names_js), [], "review shell has unnamed interactive controls")
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
