"""Document classification: a file the AI skipped is not "other", and finished batches survive a later failure."""

import unittest

import _support

content = _support.load("content")
llm = _support.load("llm")


class Scripted:
    """A model that returns the next prepared reply, or raises it if it is an error."""
    model = "test"

    def __init__(self, *replies):
        self.replies = list(replies)

    def chat_json(self, system, user, max_tokens=None):
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def items(*pairs):
    return {"items": [{"id": i, "category": cat, "summary": f"file {i}"} for i, cat in pairs]}


PROMPTS = [("system", "batch 1"), ("system", "batch 2")]


class Batches(unittest.TestCase):
    def test_skipped_file_gets_no_category(self):
        got = content.ask(Scripted(items((1, "bills"), (3, "other"))), PROMPTS[:1], [3], 100)
        self.assertEqual(got, [("bills", "file 1"), None, ("other", "file 3")])   # 2 was skipped; 3 really is "other"

    def test_unknown_category_and_stray_ids(self):
        got = content.ask(Scripted(items((1, "nonsense"), (7, "bills"), ("x", "bills"))), PROMPTS[:1], [2], 100)
        self.assertEqual(got, [("other", "file 1"), None])

    def test_malformed_replies_answer_nothing(self):
        for reply in ([], {"items": "none"}, {"items": ["bills", 3, None]}, {}):
            with self.subTest(reply=reply):
                self.assertEqual(content.ask(Scripted(reply), PROMPTS[:1], [2], 100), [None, None])

    def test_each_batch_is_handed_over_as_it_finishes(self):
        seen = []
        content.ask(Scripted(items((1, "bills"), (2, "travel")), items((1, "bank"))), PROMPTS, [2, 1], 100,
                    on_batch=lambda start, answers: seen.append((start, answers)))
        self.assertEqual(seen, [(0, [("bills", "file 1"), ("travel", "file 2")]), (2, [("bank", "file 1")])])

    def test_finished_batches_survive_a_later_failure(self):
        seen = []
        model = Scripted(items((1, "bills"), (2, "travel")), llm.LLMError("Example AI timed out."))
        with self.assertRaises(llm.LLMError):
            content.ask(model, PROMPTS, [2, 1], 100, on_batch=lambda start, answers: seen.append((start, answers)))
        self.assertEqual(seen, [(0, [("bills", "file 1"), ("travel", "file 2")])])


if __name__ == "__main__":
    unittest.main()
