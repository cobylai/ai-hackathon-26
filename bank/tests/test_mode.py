"""Demo/live mode: the setting file, the env override, and each mode's defaults."""
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bank import mode, store


class Mode(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.file = Path(self.tmp.name) / "mode"
        clean = {k: v for k, v in os.environ.items()
                 if k not in ("FLUX_MODE", "FLUX_BANK_DIR", "MUSE_BANK_DIR")}
        self.env = mock.patch.dict(os.environ, {**clean, "FLUX_MODE_FILE": str(self.file)}, clear=True)
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_no_file_is_live(self):
        self.assertEqual(mode.current(), "live")
        self.assertEqual(mode.bank_default(), Path("~/flux-bank").expanduser())
        self.assertEqual(store.bank_dir(), Path("~/flux-bank").expanduser())
        self.assertEqual(mode.calendar(), "")
        self.assertEqual(mode.reminders(), "")
        self.assertEqual(mode.label(), "Your data")

    def test_demo_file(self):
        mode.set_mode("demo")
        self.assertEqual(self.file.read_text().strip(), "demo")
        self.assertEqual(mode.current(), "demo")
        self.assertEqual(store.bank_dir(), Path("~/flux-demo-bank").expanduser())
        self.assertEqual(mode.calendar(), "Flux demo")
        self.assertEqual(mode.label(), "Demo data")
        mode.set_mode("live")
        self.assertEqual(mode.current(), "live")

    def test_live_calendar(self):
        self.assertEqual(mode.calendar(), "")
        mode.set_calendar("Home")
        self.assertEqual(mode.calendar(), "Home")
        mode.set_mode("demo")
        self.assertEqual(mode.calendar(), "Flux demo")
        with self.assertRaises(ValueError):
            mode.set_calendar("Flux demo")

    def test_env_wins(self):
        mode.set_mode("demo")
        with mock.patch.dict(os.environ, {"FLUX_MODE": "live"}):
            self.assertEqual(mode.current(), "live")
        with mock.patch.dict(os.environ, {"FLUX_BANK_DIR": "/tmp/somewhere"}):
            self.assertEqual(store.bank_dir(), Path("/tmp/somewhere"))

    def test_bad_values(self):
        self.file.write_text("staging\n")
        self.assertEqual(mode.current(), "live")
        with self.assertRaises(ValueError):
            mode.set_mode("staging")


if __name__ == "__main__":
    unittest.main()
