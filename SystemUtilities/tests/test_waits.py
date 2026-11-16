"""Nothing waits for ever: a scan always reports how it ended, and waits on other programs have a deadline."""

import queue
import subprocess
import tempfile
import time
import types
import unittest
from unittest import mock

import _support

for _name in ("agent_memory", "cleanup", "content", "perf", "quickclean", "sysinfo"):
    _support.load(_name)
core = _support.load("core")
if not hasattr(subprocess, "CREATE_NO_WINDOW"):     # a Windows-only constant drivers.py reads when it loads
    subprocess.CREATE_NO_WINDOW = 0
drivers = _support.load("drivers")
import agent


def boom(*args, **kwargs):
    raise ValueError("boom")


class ScannerEnds(unittest.TestCase):
    def last_message(self, scanner, q):
        scanner.run()
        messages = []
        while not q.empty():
            messages.append(q.get())
        return messages[-1]

    def test_normal_scan_ends_with_done(self):
        with tempfile.TemporaryDirectory() as folder:
            q = queue.Queue()
            self.assertEqual(self.last_message(core.Scanner(folder, q), q)[0], "done")

    def test_cancelled_scan_says_so(self):
        q = queue.Queue()
        scanner = core.Scanner("anywhere", q)
        scanner.cancelled = True
        self.assertEqual(self.last_message(scanner, q), ("cancelled",))

    def test_crashed_scan_says_why(self):
        q = queue.Queue()
        scanner = core.Scanner("anywhere", q)
        with mock.patch.object(core.os, "scandir", boom):
            self.assertEqual(self.last_message(scanner, q), ("failed", "boom"))
        self.assertEqual(scanner.error, "boom")

    def test_failed_rescan_leaves_the_tree_alone(self):
        old = types.SimpleNamespace(size=5, cloud=0, file_count=1, dirs=[], files=[("a", 5, 0, False)], denied=False)
        root = types.SimpleNamespace(find=lambda path: old)
        with mock.patch.object(core.os, "scandir", boom):
            self.assertIsNone(core.refresh_path(root, "anywhere"))       # and it returns instead of waiting
        self.assertEqual((old.size, old.files), (5, [("a", 5, 0, False)]))


class WaitForScan(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(agent.sysinfo, "live", lambda: {}, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.api = types.SimpleNamespace(_settings={}, _emit=lambda *a: None, _root=None, _scanner=None)
        self.agent = agent.Agent(self.api, object())

    def scanner(self, alive=False, cancelled=False, error=None):
        self.api._scanner = types.SimpleNamespace(is_alive=lambda: alive, cancelled=cancelled, error=error)

    def wait(self, **limits):
        started = time.time()
        try:
            self.agent._wait_for_scan(poll=0.01, **limits)
        finally:
            self.assertLess(time.time() - started, 2)       # every case ends promptly

    def test_finished_scan_with_a_result(self):
        self.scanner()
        self.api._root = object()
        self.wait()

    def test_failed_scan(self):
        self.scanner(error="boom")
        with self.assertRaisesRegex(RuntimeError, "the scan failed: boom"):
            self.wait()

    def test_cancelled_scan(self):
        self.scanner(cancelled=True)
        with self.assertRaisesRegex(RuntimeError, "cancelled"):
            self.wait()

    def test_scan_that_ended_with_nothing(self):
        self.scanner()
        with self.assertRaisesRegex(RuntimeError, "stopped without a result"):
            self.wait(handover=0.05)

    def test_result_that_arrives_just_after_the_scan_ends(self):
        self.scanner()
        handed_over = time.time() + 0.05

        class Api(types.SimpleNamespace):
            @property
            def _root(self):
                return object() if time.time() >= handed_over else None
        self.agent.api = Api(_scanner=self.api._scanner)
        self.wait(handover=1)

    def test_scan_that_never_ends(self):
        self.scanner(alive=True)
        with self.assertRaisesRegex(RuntimeError, "stopped waiting"):
            self.wait(limit=0.05)


class ElevatedWait(unittest.TestCase):
    STILL_RUNNING, EXITED = 0x102, 0

    def run_with(self, states, **kwargs):
        """states: what each 500 ms wait reports, in turn; the last one repeats."""
        states, closed, ticks = list(states), [], []

        def wait(handle, ms):
            time.sleep(0.005)
            return states.pop(0) if len(states) > 1 else states[0]
        windows = types.SimpleNamespace(
            shell32=types.SimpleNamespace(ShellExecuteExW=lambda info: 1),
            kernel32=types.SimpleNamespace(WaitForSingleObject=wait, CloseHandle=lambda handle: closed.append(handle)))
        with mock.patch.object(drivers.ctypes, "windll", windows, create=True):
            try:
                drivers.run_elevated("tool.exe", "", lambda: ticks.append(1), **kwargs)
            finally:
                self.assertEqual(len(closed), 1)            # the handle is released either way
        return ticks

    def test_returns_when_the_program_exits(self):
        ticks = self.run_with([self.STILL_RUNNING, self.STILL_RUNNING, self.EXITED], timeout=5)
        self.assertEqual(len(ticks), 2)

    def test_stops_waiting_at_the_deadline(self):
        with self.assertRaises(TimeoutError) as caught:
            self.run_with([self.STILL_RUNNING], timeout=0.05, what="The driver install")
        self.assertIn("The driver install didn't finish", str(caught.exception))
        self.assertIn("may still be running", str(caught.exception))

    def test_every_caller_sets_a_deadline(self):
        found = 0
        for module in ("drivers", "perf", "quickclean"):
            with open(f"{_support.APP}/{module}.py", encoding="utf-8") as f:
                source = f.read()
            at = source.find("run_elevated(")
            while at != -1:
                end, depth = at + len("run_elevated("), 1
                while depth:                              # walk to the call's closing bracket
                    depth += {"(": 1, ")": -1}.get(source[end], 0)
                    end += 1
                call = source[at:end]
                if not source[:at].endswith("def "):
                    found += 1
                    with self.subTest(module=module, call=call[:60]):
                        self.assertIn("timeout=", call)
                at = source.find("run_elevated(", end)
        self.assertEqual(found, 4)


if __name__ == "__main__":
    unittest.main()
