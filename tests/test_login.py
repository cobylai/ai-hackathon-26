import os

from harness.browser.login import profile_locked


def test_no_lock_means_free(tmp_path):
    assert not profile_locked(tmp_path)


def test_stale_lock_is_free(tmp_path):
    os.symlink("host-99999999", tmp_path / "SingletonLock")
    assert not profile_locked(tmp_path)


def test_live_lock_is_locked(tmp_path):
    os.symlink(f"host-{os.getpid()}", tmp_path / "SingletonLock")
    assert profile_locked(tmp_path)
