"""Check the B8 handoff without an account: visible window -> hidden session.

Run on the desktop (it opens one Chromium window for a few seconds):

    uv run python scripts/check_login_flow.py

It serves a local page that sets a persistent cookie, opens it in the same
visible Chromium that ``login`` uses, closes it, then reads the page headless
on the same profile. If the hidden session reports ``AUTH signed=yes``, the
profile, keychain mode and cookie storage all survive the handoff, and only the
site's own sign-in policy is left to test.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from harness.browser.session import Session  # noqa: E402


class Handler(BaseHTTPRequestHandler):
    hits: list[bool] = []

    def log_message(self, *args):  # keep the output tidy
        pass

    def do_GET(self):
        authed = "signed=yes" in self.headers.get("Cookie", "")
        self.hits.append(authed)
        body = "AUTH signed=yes" if authed else "AUTH signed=no"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        if not authed:
            self.send_header("Set-Cookie", "signed=yes; Path=/; Max-Age=3600")
        self.end_headers()
        self.wfile.write(
            f"<html><head><title>Auth</title></head><body>{body}</body></html>".encode()
        )


def wait_for(predicate, timeout: float, step: float = 0.2) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(step)
    return False


def close_browser(profile: Path) -> None:
    lock = profile / "SingletonLock"
    if lock.is_symlink():
        try:
            os.kill(int(os.readlink(lock).rsplit("-", 1)[-1]), signal.SIGTERM)
        except (ValueError, ProcessLookupError, OSError):
            pass


def main() -> int:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    profile = Path(tempfile.mkdtemp(prefix="login-flow-"))
    child = None
    try:
        code = (
            "import sys\n"
            "from harness.browser.login import login\n"
            f"sys.exit(login({url!r}, {str(profile)!r}, verify=False))\n"
        )
        child = subprocess.Popen([sys.executable, "-c", code], cwd=str(ROOT))
        if not wait_for(lambda: bool(Handler.hits), timeout=30):
            print("ERR the visible window never loaded the page")
            return 1
        print("OK visible window set a persistent cookie")

        close_browser(profile)
        child.terminate()
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill()
        # Chromium may keep the lock briefly (or leave a stale one); retry the
        # hidden start the same way `login` does.
        session = Session(profile)
        for attempt in range(20):
            try:
                session.start()
                break
            except Exception:
                if attempt == 19:
                    print("ERR the hidden session could not start on this profile")
                    return 1
                time.sleep(0.5)
        try:
            session.page.goto(url, wait_until="domcontentloaded", timeout=20000)
            text = session.page.inner_text("body").strip()
        finally:
            session.stop()
        if "AUTH signed=yes" in text:
            print("OK hidden session sees the signed-in cookie")
            return 0
        print(f"ERR hidden session sees {text!r}, so the handoff did not carry the cookie")
        return 1
    finally:
        if child is not None and child.poll() is None:
            child.kill()
        server.shutdown()
        server.server_close()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
