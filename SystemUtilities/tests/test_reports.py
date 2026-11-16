"""Jarvis says "Done" only when it is done, and a failed check is never reported as an all-clear."""

import types
import unittest
from unittest import mock

import _support

for _name in ("agent_memory", "content", "perf", "quickclean", "sysinfo"):
    _support.load(_name)
cleanup = _support.load("cleanup")
organiser = _support.load("organiser")
import agent

MB = 1024 ** 2


def action_for(item, cat):          # the agent looks this up in the module that defines the Api class
    return "recycle"


class Mem:
    def __init__(self):
        self.records = []

    def record(self, kind, category, answer, *rest):
        self.records.append((kind, answer))

    def log_request(self, text, intent):
        pass

    def policy(self, kind, category):
        return "default"

    def rules_summary(self):
        return []

    def check_signatures(self):
        pass

    def suspicious(self):
        return []


class Api:
    _settings, _ai_enabled, _llm, _ai_cat = {}, False, None, None

    def __init__(self):
        self._cats = []

    def _emit(self, event, data):
        pass

    def known_folders(self):
        return []


class Case(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(agent.sysinfo, "live", lambda: {}, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.api = Api()
        self.agent = agent.Agent(self.api, Mem())


class Outcome(unittest.TestCase):
    def test_wording(self):
        self.assertEqual(agent.outcome("Freed 2 GB"), "Done. Freed 2 GB.")
        self.assertEqual(agent.outcome("Freed 2 GB", [0, "3 files in use were skipped"]),
                         "Done. Freed 2 GB; 3 files in use were skipped.")
        self.assertEqual(agent.outcome("Freed 1 GB", ["1 item of 4 couldn't be removed"], 1, 4),
                         "Partly done. Freed 1 GB; 1 item of 4 couldn't be removed.")
        self.assertEqual(agent.outcome("Freed 0 KB", ["4 items of 4 couldn't be removed"], 4, 4),
                         "That didn't work. Freed 0 KB; 4 items of 4 couldn't be removed.")


class JunkClean(Case):
    def run_clean(self, results):
        targets = [{"id": "temp", "name": "Temp files"}, {"id": "cache", "name": "Caches"}]
        sizes = {"temp": {"size": 300 * MB}, "cache": {"size": 200 * MB}}
        self.api.quick_clean = lambda ids: {"freed": sum(r["freed"] for r in results),
                                            "skipped": sum(r["skipped"] for r in results), "results": results}
        with mock.patch.object(self.agent, "_junk", lambda: (targets, sizes)):
            return self.agent.t_junk({}).pending.run()

    def test_all_cleaned(self):
        say = self.run_clean([{"id": "temp", "freed": 300 * MB, "skipped": 0}, {"id": "cache", "freed": 200 * MB, "skipped": 0}])
        self.assertEqual(say, "Done. Freed 500 MB.")

    def test_one_area_failed(self):
        say = self.run_clean([{"id": "temp", "freed": 300 * MB, "skipped": 2},
                              {"id": "cache", "freed": 0, "skipped": 0, "error": "Access is denied"}])
        self.assertEqual(say, "Partly done. Freed 300 MB; 2 files in use were skipped; 1 area of 2 couldn't be cleaned.")

    def test_every_area_failed(self):
        say = self.run_clean([{"id": i, "freed": 0, "skipped": 0, "error": "Access is denied"} for i in ("temp", "cache")])
        self.assertTrue(say.startswith("That didn't work."), say)


class Deletable(Case):
    def prepare(self, ai_error=None):
        paths = [r"C:\Temp\a", r"C:\Temp\b", r"C:\Temp\c"]
        cat = types.SimpleNamespace(source="rule", name="Temporary files", risk=cleanup.SAFE, total=300 * MB,
                                    items=[{"path": p, "size": 100 * MB} for p in paths])
        self.api._cats = [cat]
        self.api.find_candidates = lambda: []
        if ai_error:
            self.api._ai_enabled, self.api._llm = True, object()
            self.api.ai_review = lambda: {"__error__": ai_error}
        with mock.patch.object(self.agent, "folder", lambda name: r"C:\Temp"), \
                mock.patch.object(self.agent, "_scan", lambda path: None):
            return self.agent.t_deletable({})

    def test_result_counts_failures_and_skipped_files(self):
        reply = self.prepare()
        answers = iter([{"freed": 100 * MB, "skipped": 4}, {"__error__": "in use"}, {"freed": 100 * MB, "skipped": 0}])
        self.api.clean_item = lambda path: next(answers)
        self.assertEqual(reply.pending.run(),
                         "Partly done. Freed 200 MB; 4 files in use were skipped; 1 item of 3 couldn't be removed.")

    def test_failed_ai_check_is_mentioned(self):
        reply = self.prepare(ai_error="Example AI timed out.")
        self.assertIn("AI check of the big folders didn't finish (Example AI timed out)", reply.say)
        self.assertIn("Shall I clean them?", reply.say)

    def test_no_note_when_ai_is_off(self):
        self.assertNotIn("AI check", self.prepare().say)


class Suspicious(Case):
    def test_failed_check_is_not_an_all_clear(self):
        self.api.perf_snapshot = lambda: {"__error__": "Access is denied."}
        say = self.agent.t_suspicious({}).say
        self.assertIn("couldn't check what's running", say)
        self.assertIn("Access is denied", say)
        self.assertNotIn("Every program", say)

    def test_clean_check_is_an_all_clear(self):
        self.api.perf_snapshot = lambda: {"groups": []}
        self.agent.mem.sample_processes = lambda *a: None
        with mock.patch.object(agent.agent_memory, "foreground_exe", lambda: None, create=True), \
                mock.patch.object(agent.agent_memory, "internet_pids", lambda: set(), create=True):
            self.assertTrue(self.agent.t_suspicious({}).say.startswith("Nothing running looks suspicious."))


class UnexpectedInput(Case):
    def test_unexpected_error_still_gets_an_answer(self):
        with mock.patch.object(self.agent, "_answer", side_effect=KeyError("desc")):
            reply = self.agent.ask("what's running")
        self.assertEqual(reply["say"], "Sorry, something went wrong with that request (KeyError).")

    def test_model_arguments_of_the_wrong_shape_are_dropped(self):
        for args in ([1, 2], "downloads", 5, None):
            with self.subTest(args=args):
                self.api._ai_enabled = True
                self.api._llm = types.SimpleNamespace(chat_json=lambda *a, **k: {"tool": "junk", "args": args})
                self.assertEqual(self.agent._intent("blorp the thing"), ("junk", {}))

    def test_folder_name_that_is_not_text(self):
        with self.assertRaises(ValueError):          # a clear "couldn't find a folder", not an AttributeError
            self.agent.folder(["downloads"])


class EmptyPlan(unittest.TestCase):
    def plan(self, reply):
        model = types.SimpleNamespace(chat_json=lambda *a, **k: reply)
        with mock.patch.object(organiser, "plan_prompt", lambda profile: ("system", "user")):
            return organiser.ai_organise(model, {})

    def test_empty_plans_are_errors(self):
        for reply in ({}, [], {"summary": "  ", "moves": "none"}, {"tips": ["Name files with a date"]}):
            with self.subTest(reply=reply), self.assertRaises(RuntimeError):
                self.plan(reply)

    def test_a_plan_with_nothing_to_move_is_fine(self):
        plan = self.plan({"summary": "Already tidy: everything sits in folders."})
        self.assertEqual((plan["moves"], plan["structure"]), ([], []))


if __name__ == "__main__":
    unittest.main()
