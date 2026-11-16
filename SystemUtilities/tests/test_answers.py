"""Jarvis: what counts as a yes, and which question a yes answers."""

import time
import unittest
from unittest import mock

import _support

for _name in ("agent_memory", "cleanup", "content", "perf", "quickclean", "sysinfo"):
    _support.load(_name)
import agent


class Mem:
    def __init__(self):
        self.records = []

    def record(self, kind, category, answer, *rest):
        self.records.append((kind, answer))

    def log_request(self, text, intent):
        pass

    def policy(self, kind, category):
        return "default"


class Api:
    _settings, _ai_enabled, _llm = {}, False, None

    def __init__(self):
        self.events = []

    def _emit(self, event, data):
        self.events.append((event, data))


class AnswerKind(unittest.TestCase):
    CASES = {
        "yes": ["yes", "Yes please", "ok, go ahead", "okay do it now", "yeah, clean it up", "right", "sure thanks", "Yes."],
        "no": ["no", "no thanks", "don't", "cancel that", "stop"],
        "review": ["show me", "show me the files first", "ok, show me the files first", "sure, let me see what's in it",
                   "right, let me check before you delete anything", "okay, open it so I can look",
                   "no, show me the list", "correct, but review them first", "ok but first show me"],
        "unclear": ["yes, but don't delete the bills", "ok what about the downloads folder", "yes clean the junk"],
        None: ["what's running", "organise my downloads", ""],
    }

    def test_phrases(self):
        for want, phrases in self.CASES.items():
            for text in phrases:
                with self.subTest(text=text):
                    self.assertEqual(agent.answer_kind(text), want)


class WaitingQuestion(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(agent.sysinfo, "live", lambda: {}, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.agent = agent.Agent(Api(), Mem())
        self.ran = []
        self.question = self.ask_question("junk", "Shall I clean it?", 1)

    def ask_question(self, kind, text, marker):
        p = agent.Pending(kind, text, lambda: self.ran.append(marker) or "Done.", ["a", "b"], review={"view": "quick"})
        self.agent._set_pending(p)
        return p

    def settle(self):
        deadline = time.time() + 2
        while self.agent.job and time.time() < deadline:
            time.sleep(0.01)

    # ---- spoken / typed answers
    def test_plain_yes_runs_the_change(self):
        self.agent.ask("yes please")
        self.settle()
        self.assertEqual((self.ran, self.agent.pending, self.agent.mem.records), ([1], None, [("junk", "yes")]))

    def test_asking_to_see_first_runs_nothing(self):
        self.agent.ask("ok, show me the files first")
        self.settle()
        self.assertEqual((self.ran, self.agent.mem.records), ([], [("junk", "review")]))

    def test_unclear_yes_runs_nothing_and_asks_again(self):
        reply = self.agent.ask("yes, but don't delete the bills")
        self.settle()
        self.assertEqual((self.ran, self.agent.mem.records), ([], []))
        self.assertIs(self.agent.pending, self.question)
        self.assertTrue(reply["expect_reply"])

    def test_no_declines(self):
        self.agent.ask("no thanks")
        self.assertEqual((self.ran, self.agent.pending, self.agent.mem.records), ([], None, [("junk", "no")]))

    def test_yes_while_busy_keeps_the_question_and_learns_nothing(self):
        self.agent.job = "Scanning your Downloads"
        self.agent.ask("yes")
        self.assertEqual((self.ran, self.agent.mem.records), ([], []))
        self.assertIs(self.agent.pending, self.question)
        self.agent.job = None
        self.agent.ask("yes")
        self.settle()
        self.assertEqual((self.ran, self.agent.mem.records), ([1], [("junk", "yes")]))

    # ---- button clicks name the question they answer
    def test_question_shows_its_id(self):
        self.assertEqual(self.agent.state()["pending"]["id"], self.question.id)

    def test_click_on_a_replaced_question_does_nothing(self):
        newer = self.ask_question("files", "Delete 40 files in Downloads?", 2)
        for click in (lambda: self.agent.confirm("click", self.question.id), lambda: self.agent.decline(self.question.id),
                      lambda: self.agent.review(self.question.id)):
            reply = click()
            self.settle()
            self.assertIn("haven't done anything", reply.say)
            self.assertEqual((self.ran, self.agent.mem.records), ([], []))
            self.assertIs(self.agent.pending, newer)
        self.assertEqual(self.agent.api.events[-1], ("agent_pending", newer.public()))   # the panel is put right

    def test_click_on_the_current_question_runs_it(self):
        newer = self.ask_question("files", "Delete 40 files in Downloads?", 2)
        self.agent.confirm("click", newer.id)
        self.settle()
        self.assertEqual((self.ran, self.agent.pending), ([2], None))

    def test_click_after_the_question_went_away_does_nothing(self):
        self.agent._set_pending(None)
        reply = self.agent.confirm("click", self.question.id)
        self.settle()
        self.assertEqual(self.ran, [])
        self.assertIn("no longer waiting", reply.say)


if __name__ == "__main__":
    unittest.main()
