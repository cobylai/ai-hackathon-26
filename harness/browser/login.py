"""Sign-in mode (B8): a plain, visible Chromium on the harness profile.

Google refuses sign-in when it sees a debugging port or an automated tab, so
this starts the bundled Chromium directly with no automation flags. The user
signs in, closes the window, and the hidden session reuses the same profile.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

from harness import config


def profile_locked(profile_dir: Path) -> bool:
    """True if a live Chromium process holds this profile (SingletonLock)."""
    lock = profile_dir / "SingletonLock"
    if not lock.is_symlink():
        return False
    try:
        pid = int(os.readlink(lock).rsplit("-", 1)[-1])
        os.kill(pid, 0)
    except (ValueError, ProcessLookupError, OSError):
        return False  # stale lock from a dead process
    return True


def chromium_path() -> str:
    """Path of the Chromium binary Playwright installed (nothing is launched)."""
    with sync_playwright() as p:
        return p.chromium.executable_path


def _verify(url: str, profile: Path, attempts: int = 20) -> str:
    """Open the profile headless and report whether the site looks signed in.

    Chromium can take several seconds to release the profile after the visible
    window closes (measured up to ~15 s on an abrupt close), so a failed start is
    retried for up to ~10 s.
    """
    from harness.browser.session import Session
    from harness.browser.state import classify

    domain = urlparse(url).netloc or "local"
    last_error = ""
    for _ in range(attempts):
        session = Session(profile)
        try:
            session.start()
        except Exception as exc:
            last_error = " ".join(str(exc).split())[:80]
            session.stop()
            time.sleep(0.5)
            continue
        try:
            response = session.page.goto(url, wait_until="domcontentloaded", timeout=20000)
            word = classify(session.page, status=response.status if response else None)
            title = " ".join(session.page.title().split())[:60] or "(untitled)"
            return f"{word} {domain} | {title} | sign-in check"
        except Exception as exc:
            message = " ".join(str(exc).split())[:80]
            return f"ERR {domain} | sign-in check failed | {message}"
        finally:
            session.stop()
    return f"ERR {domain} | could not start the browser after sign-in | {last_error}"


def login(url: str, profile_dir: Path | None = None, verify: bool = True) -> int:
    """Open a visible Chromium on the profile, then check the signed-in state."""
    from harness.browser.session import get_session

    profile = Path(profile_dir) if profile_dir else config.PROFILE_DIR
    get_session().stop()  # release the hidden session first
    if profile_locked(profile):
        print("ERR profile is in use by another Chromium; close it and retry")
        return 1
    profile.mkdir(parents=True, exist_ok=True)
    print(f"OK opening a visible window on {profile}; sign in, then close it")
    cmd = [
        chromium_path(),
        f"--user-data-dir={profile}",
        # Same keychain mode as Playwright's hidden session, so cookies saved
        # here decrypt there and macOS never asks for the real keychain.
        "--use-mock-keychain",
        "--password-store=basic",
        "--no-first-run",
        "--no-default-browser-check",
        url,
    ]
    code = subprocess.run(cmd).returncode
    if not verify:
        return code
    print("OK window closed; checking the profile in the hidden session...")
    result = _verify(url, profile)
    print(result)
    return 0 if result.startswith("OK") else 1
