"""Every reason test runs against a temporary bank and chats folder, never $HOME.

The window server saves the open chat after every /ask (reason/chats.py), and a test that
builds a handler without chats_root would otherwise write into ~/flux-chats (it did:
test_suggest's window test left 23 chats there). Set before any test module is imported.
"""
import atexit
import os
import shutil
import tempfile

_TMP = tempfile.mkdtemp(prefix="flux-tests-")
atexit.register(shutil.rmtree, _TMP, True)
for _k in ("FLUX_CHATS_DIR", "MUSE_CHATS_DIR"):
    os.environ[_k] = os.path.join(_TMP, "chats")
for _k in ("FLUX_BANK_DIR", "MUSE_BANK_DIR"):
    os.environ[_k] = os.path.join(_TMP, "bank")
