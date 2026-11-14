"""Sign-in mode (B8): a plain, visible Chromium on the harness profile.

Google refuses sign-in when it sees a debugging port or an automated tab, so
this starts the bundled Chromium directly with no automation flags. The user
signs in, closes the window, and the hidden session reuses the same profile.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

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


def login(url: str, profile_dir: Path | None = None) -> int:
    """Open a visible Chromium on the profile and wait until it is closed."""
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
    return subprocess.run(cmd).returncode
