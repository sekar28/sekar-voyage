"""AI providers: a reply that was cut off, refused or empty must not be used as if it were a complete answer.

Each provider is fed canned replies - no network and no API key.
"""

import types
import unittest
from unittest import mock

import _support

llm = _support.load("llm")                      # the alias for shared/sekar_common/llm.py
llm_anthropic = _support.load("llm_anthropic")

JSON_OK = '{"tool": "junk", "args": {}}'


class Endings:
    """The same checks for every provider. A subclass says how to make that provider return a given reply."""

    def reply(self, text, ending):                 # ending: "stop" | "length" | "blocked"
        raise NotImplementedError

    def chat(self, text, ending, json_mode=False):
        client = self.reply(text, ending)
        return client.chat_json("system", "user") if json_mode else client.chat("system", "user")

    def test_complete_answer(self):
        self.assertEqual(self.chat("  All good.  ", "stop"), "All good.")
        self.assertEqual(self.chat(JSON_OK, "stop", json_mode=True), {"tool": "junk", "args": {}})

    def test_cut_off_json_is_an_error_that_keeps_the_partial_text(self):
        with self.assertRaises(llm.LLMTruncated) as caught:
            self.chat('{"items": [{"id": 1, "category": "bills"}, {"id": 2, "categ', "length", json_mode=True)
        self.assertEqual(caught.exception.kind, "truncated")
        self.assertTrue(caught.exception.partial.startswith('{"items"'))
        self.assertNotIn("items", str(caught.exception))        # the message is safe to show or speak

    def test_cut_off_json_that_happens_to_parse_is_still_an_error(self):
        with self.assertRaises(llm.LLMTruncated):
            self.chat(JSON_OK, "length", json_mode=True)

    def test_cut_off_text_is_marked(self):
        self.assertEqual(self.chat("This folder holds", "length"), "This folder holds" + llm.CUT_MARK)

    def test_nothing_before_the_limit(self):
        with self.assertRaises(llm.LLMTruncated):
            self.chat("", "length")

    def test_empty_answer(self):
        for json_mode in (False, True):
            with self.assertRaises(llm.LLMEmpty) as caught:
                self.chat("   ", "stop", json_mode=json_mode)
            self.assertEqual(caught.exception.kind, "empty")

    def test_answer_in_the_wrong_format(self):
        with self.assertRaises(llm.LLMBadFormat) as caught:
            self.chat("Sure! I would clean the junk.", "stop", json_mode=True)
        self.assertEqual(caught.exception.raw, "Sure! I would clean the junk.")
        self.assertNotIn("Sure!", str(caught.exception))         # raw model text stays out of the message

    def test_every_failure_is_still_an_llm_error(self):
        for kind in (llm.LLMTruncated, llm.LLMBlocked, llm.LLMEmpty, llm.LLMBadFormat):
            self.assertTrue(issubclass(kind, llm.LLMError))


class OllamaEndings(Endings, unittest.TestCase):
    def reply(self, text, ending):
        body = {"message": {"content": text}, "done_reason": ending, "prompt_eval_count": 5, "eval_count": 7}
        patcher = mock.patch.object(llm, "_http", lambda *a, **k: body)
        patcher.start()
        self.addCleanup(patcher.stop)
        return llm.Ollama(model="qwen3")

    def test_missing_message(self):
        with mock.patch.object(llm, "_http", lambda *a, **k: {"message": None}):
            with self.assertRaises(llm.LLMEmpty):
                llm.Ollama(model="qwen3").chat("system", "user")


class OpenAIEndings(Endings, unittest.TestCase):
    def serve(self, body):
        patcher = mock.patch.object(llm, "_http", lambda *a, **k: body)
        patcher.start()
        self.addCleanup(patcher.stop)
        return llm.OpenAICompatible("https://api.example.test/v1", "key", model="gpt-test", name="Example AI")

    def reply(self, text, ending):
        finish = {"blocked": "content_filter"}.get(ending, ending)
        return self.serve({"choices": [{"message": {"content": text}, "finish_reason": finish}],
                           "usage": {"prompt_tokens": 5, "completion_tokens": 7}})

    def test_filtered(self):
        with self.assertRaises(llm.LLMBlocked) as caught:
            self.chat("", "blocked")
        self.assertIn("Example AI declined", str(caught.exception))

    def test_refusal_field(self):
        client = self.serve({"choices": [{"message": {"content": None, "refusal": "I can't help with that."},
                                          "finish_reason": "stop"}]})
        with self.assertRaises(llm.LLMBlocked):
            client.chat_json("system", "user")

    def test_no_choices(self):
        with self.assertRaises(llm.LLMEmpty):
            self.serve({"choices": []}).chat("system", "user")


class FakeSdk(types.SimpleNamespace):
    """Just the error classes llm_anthropic.py names, with the real SDK's parent/child order."""

    def __init__(self):
        class APIError(Exception):
            pass

        class APIConnectionError(APIError):
            pass

        class APITimeoutError(APIConnectionError):
            pass

        class APIStatusError(APIError):
            status_code, message = 500, "server error"
        status = {name: type(name, (APIStatusError,), {}) for name in
                  ("AuthenticationError", "PermissionDeniedError", "NotFoundError", "RateLimitError")}
        super().__init__(APIError=APIError, APIConnectionError=APIConnectionError, APITimeoutError=APITimeoutError,
                         APIStatusError=APIStatusError, **status)


class ClaudeEndings(Endings, unittest.TestCase):
    def setUp(self):
        self.sdk = FakeSdk()
        patcher = mock.patch.object(llm_anthropic, "anthropic", self.sdk)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.calls = []

    def client(self, respond, model="claude-haiku-4-5"):
        def create(**params):
            self.calls.append(params)
            return respond()
        claude = llm_anthropic.Claude.__new__(llm_anthropic.Claude)      # no SDK and no key needed
        llm.BaseClient.__init__(claude, model)
        messages = types.SimpleNamespace(create=create)
        claude.client = types.SimpleNamespace(messages=messages, beta=types.SimpleNamespace(messages=messages))
        return claude

    def reply(self, text, ending):
        stop = {"stop": "end_turn", "length": "max_tokens", "blocked": "refusal"}[ending]
        blocks = [types.SimpleNamespace(type="thinking", thinking="hmm"), types.SimpleNamespace(type="text", text=text)]
        return self.client(lambda: types.SimpleNamespace(
            content=blocks, stop_reason=stop, usage=types.SimpleNamespace(input_tokens=5, output_tokens=7)))

    def test_refusal(self):
        with self.assertRaises(llm.LLMBlocked) as caught:
            self.chat("", "blocked")
        self.assertEqual(str(caught.exception), "Claude declined this request.")

    def test_callers_timeout_is_used_up_to_the_limit(self):
        client = self.reply("ok", "stop")
        client.chat("system", "user", timeout=60)
        client.chat("system", "user", timeout=600)
        client.chat("system", "user")
        self.assertEqual([c["timeout"] for c in self.calls], [60, llm_anthropic.MAX_WAIT, llm_anthropic.MAX_WAIT])

    def test_small_token_caps_do_not_shrink_the_budget(self):
        client = self.reply("ok", "stop")
        client.chat("system", "user", max_tokens=300)        # thinking shares the budget: 300 would cut the answer off
        client.chat("system", "user", max_tokens=32000)
        self.assertEqual([c["max_tokens"] for c in self.calls], [llm_anthropic.MAX_TOKENS, 32000])

    def test_timeout_says_timed_out(self):
        def fail():
            raise self.sdk.APITimeoutError()
        with self.assertRaises(llm.LLMError) as caught:
            self.client(fail).chat("system", "user", timeout=60)
        self.assertIn("timed out", str(caught.exception))
        self.assertIn("60 s", str(caught.exception))

    def test_connection_failure_is_not_called_a_timeout(self):
        def fail():
            raise self.sdk.APIConnectionError()
        with self.assertRaises(llm.LLMError) as caught:
            self.client(fail).chat("system", "user")
        self.assertIn("Cannot reach", str(caught.exception))


class HttpReplies(unittest.TestCase):
    def serve(self, body):
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = body
        return mock.patch.object(llm.urllib.request, "urlopen", return_value=response)

    def test_readable_reply(self):
        with self.serve(b'{"ok": true}'):
            self.assertEqual(llm._http("https://api.example.test"), {"ok": True})

    def test_unreadable_reply_is_an_llm_error(self):
        for body in (b"<html>Sign in</html>", b"[1, 2]", b""):
            with self.subTest(body=body), self.serve(body):
                with self.assertRaises(llm.LLMBadFormat):
                    llm._http("https://api.example.test", what="Example AI")

    def test_timeout_says_timed_out(self):
        with mock.patch.object(llm.urllib.request, "urlopen", side_effect=TimeoutError("timed out")):
            with self.assertRaises(llm.LLMError) as caught:
                llm._http("https://api.example.test", timeout=60, what="Example AI")
        self.assertEqual(str(caught.exception), "Example AI timed out (no answer within 60 s).")


del Endings      # the shared checks run only through the provider classes above

if __name__ == "__main__":
    unittest.main()
