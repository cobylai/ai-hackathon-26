"""Real-mail sync: incremental, de-duplicated, outside git. Fake fixtures only, offline."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from bank import mailsync as M


class FakeGw:
    def __init__(self, threads):
        self.threads = threads  # {tid: (row, msgs newest-first, ids newest-first)}
        self.reads = []

    def list_threads(self, days, limit):
        return [t[0] for t in self.threads.values()]

    def read_thread(self, tid):
        self.reads.append(tid)
        return self.threads[tid][1], self.threads[tid][2]


def row(tid, date="Nov 14, 9:12 AM", snip="s"):
    return M.ThreadRow(tid, f"Subject {tid}", date, snip)


def msg(n, body):
    return (f"Pat <p{n}@example.org>", "Thu, Nov 12, 2026, 4:30 PM", body)


class Ingest:
    def __init__(self):
        self.sources = []

    def __call__(self, text, source, **kw):
        status = "duplicate" if source in self.sources else "added"
        self.sources.append(source)
        return {"status": status, "path": source}


class T(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp(prefix="flux-fake-")).resolve()

    def test_second_run_adds_only_new_mail(self):
        gw = FakeGw({"t1": (row("t1"), [msg(1, "hello")], ["m1"])})
        ing = Ingest()
        r1 = M.sync_mail(gw, ing, self.d)
        self.assertEqual((r1.threads_read, r1.added), (1, 1))
        r2 = M.sync_mail(gw, ing, self.d)
        self.assertEqual((r2.threads_skipped, r2.threads_read, r2.added), (1, 0, 0))
        self.assertEqual(gw.reads, ["t1"])
        # a reply arrives: row changes, only the new message is filed
        gw.threads["t1"] = (row("t1", "Nov 15, 8:00 AM", "re"), [msg(2, "reply"), msg(1, "hello")], ["m2", "m1"])
        r3 = M.sync_mail(gw, ing, self.d)
        self.assertEqual((r3.threads_read, r3.added, r3.messages), (1, 1, 1))
        self.assertEqual(ing.sources, ["gmail:t1:m1", "gmail:t1:m2"])

    def test_dedupes_threads_and_limit(self):
        rows = [row("a"), row("a"), row("b"), row("c")]
        gw = mock.Mock()
        gw.list_threads.return_value = rows
        gw.read_thread.side_effect = lambda t: ([msg(1, "x")], [t + "m"])
        r = M.sync_mail(gw, Ingest(), self.d, limit=2)
        self.assertEqual(r.threads_seen, 2)

    def test_budget_is_resumable(self):
        gw = FakeGw({t: (row(t), [msg(1, "x")], [t + "m"]) for t in "abc"})
        ticks = iter([0, 0, 99, 99, 99, 99, 99, 99, 99])
        r = M.sync_mail(gw, Ingest(), self.d, budget_s=10, clock=lambda: next(ticks))
        self.assertGreater(r.remaining, 0)
        r2 = M.sync_mail(gw, Ingest(), self.d)
        self.assertEqual(r.threads_read + r2.threads_read, 3)

    def test_model_errors_leave_thread_for_retry(self):
        gw = FakeGw({"t1": (row("t1"), [msg(1, "x")], ["m1"])})

        def boom(*a, **k):
            raise ConnectionError("down")
        r = M.sync_mail(gw, boom, self.d)
        self.assertEqual(r.errors, 1)
        r2 = M.sync_mail(gw, Ingest(), self.d)
        self.assertEqual(r2.added, 1)

    def test_state_has_no_content(self):
        gw = FakeGw({"t1": (row("t1", snip="secret snippet"), [msg(1, "secret body")], ["m1"])})
        M.sync_mail(gw, Ingest(), self.d)
        txt = (self.d / M.STATE_FILE).read_text()
        self.assertNotIn("secret", txt)

    def test_long_message_is_chunked_at_6000_tokens(self):
        from bank import extract
        self.assertEqual(extract.CHUNK_TOKENS, 6000)
        long = "word " * 20000
        self.assertGreater(len(extract.chunks(long)), 1)

    def test_lock_blocks_concurrent_sync(self):
        with M._Lock(self.d):
            with self.assertRaises(M.Locked):
                M.sync_mail(FakeGw({}), Ingest(), self.d)


class Safety(unittest.TestCase):
    def test_default_live_bank_is_outside_repo(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FLUX_BANK_DIR", None)
            os.environ.pop("MUSE_BANK_DIR", None)
            p = M.live_bank_dir()
        self.assertFalse(M.inside_repo(p), p)
        self.assertEqual(p, Path.home() / "flux-bank")

    def test_bank_path_inside_repo_is_refused(self):
        for bad in (M.REPO / "data" / "bank", M.REPO, M.REPO / "x" / ".." / "data"):
            with mock.patch.dict(os.environ, {"FLUX_BANK_DIR": str(bad)}):
                with self.assertRaises(SystemExit):
                    M.live_bank_dir()
            with self.assertRaises(SystemExit):
                M.sync_mail(FakeGw({}), Ingest(), bad)

    def test_repo_symlink_into_repo_is_refused(self):
        d = Path(tempfile.mkdtemp())
        link = d / "bank"
        link.symlink_to(M.REPO)
        self.assertTrue(M.inside_repo(link))

    def test_gitignore_covers_bank_and_state(self):
        for p in ("data/bank/x.md", "flux-bank/person/x.md", ".mailsync.json", "flux-demo-bank/a.md"):
            r = subprocess.run(["git", "check-ignore", "-q", p], cwd=M.REPO)
            self.assertEqual(r.returncode, 0, p)

    def test_no_bank_files_tracked(self):
        out = subprocess.run(["git", "ls-files"], cwd=M.REPO, capture_output=True, text=True).stdout.split()
        bad = [f for f in out if f.startswith(("data/bank", "flux-bank")) or f.endswith(".mailsync.json")]
        self.assertEqual(bad, [])


if __name__ == "__main__":
    unittest.main()
