"""Claude via the official Anthropic Python SDK."""

from .llm import BaseClient, LLMError

anthropic = None   # the SDK takes several seconds to import, so it loads on first use (settings only need the lists below)


def _sdk():
    global anthropic
    if anthropic is None:
        import anthropic as sdk
        anthropic = sdk
    return anthropic

DEFAULT_MODEL = "claude-opus-5-5"
# List prices per 1M tokens (input, output), USD - used only for the cost estimate shown before a request.
PRICES = {
    "claude-fable-5-1": (10.0, 50.0), "claude-fable-5": (10.0, 50.0), "claude-opus-5-5": (4.0, 20.0),
    "claude-opus-5": (5.0, 25.0), "claude-opus-4-8": (5.0, 25.0), "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0), "claude-sonnet-5-5": (2.0, 10.0), "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0), "claude-haiku-5-5": (0.10, 0.50), "claude-haiku-4-5": (1.0, 5.0),
}
SUGGESTED = ["claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5", "claude-fable-5-1"]
# Models that accept the server-side refusal fallback ("default" routing).
FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")
MAX_TOKENS = 16000     # room for adaptive thinking plus the answer; non-streaming default


class Claude(BaseClient):
    label = "Anthropic Claude"

    def __init__(self, api_key, model=None):
        super().__init__(model or DEFAULT_MODEL)
        if not api_key:
            raise LLMError("Add your Anthropic API key in AI settings.")
        self.client = _sdk().Anthropic(api_key=api_key, timeout=300.0)

    def models(self):
        try:
            names = [m.id for m in self.client.models.list()]
        except anthropic.AuthenticationError as e:
            raise LLMError("Anthropic rejected the API key.") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("Cannot reach the Anthropic API - check your internet connection.") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Anthropic API error ({e.status_code}): {e.message}") from e
        return names or SUGGESTED

    def price(self):
        return PRICES.get(self.model)

    def count_tokens(self, system, user):
        try:
            r = self.client.messages.count_tokens(model=self.model, system=system,
                                                  messages=[{"role": "user", "content": user}])
            return r.input_tokens, True
        except anthropic.APIError:
            return super().count_tokens(system, user)

    def chat(self, system, user, json_mode=False, timeout=600, max_tokens=None):
        if json_mode:
            system += "\n\nReply with the JSON object only - no prose and no code fences."
        params = dict(model=self.model, max_tokens=MAX_TOKENS, system=system,
                      messages=[{"role": "user", "content": user}],
                      output_config={"effort": "low"})      # short classification/summarising tasks
        try:
            if self.model in FALLBACK_MODELS:
                response = self.client.beta.messages.create(
                    **params, betas=["server-side-fallback-2026-07-01"], fallbacks="default")
            else:
                response = self.client.messages.create(**params)
        except anthropic.AuthenticationError as e:
            raise LLMError("Anthropic rejected the API key - update it in AI settings.") from e
        except anthropic.PermissionDeniedError as e:
            raise LLMError(f"This API key can't use {self.model}.") from e
        except anthropic.NotFoundError as e:
            raise LLMError(f"Unknown model {self.model} - pick another in AI settings.") from e
        except anthropic.RateLimitError as e:
            raise LLMError("Anthropic rate limit reached - wait a minute and try again.") from e
        except anthropic.APIStatusError as e:
            raise LLMError(f"Anthropic API error ({e.status_code}): {e.message}") from e
        except anthropic.APIConnectionError as e:
            raise LLMError("Cannot reach the Anthropic API - check your internet connection.") from e

        self._add_usage(response.usage.input_tokens, response.usage.output_tokens)
        if response.stop_reason == "refusal":
            raise LLMError("Claude declined this request.")
        return "".join(b.text for b in response.content if b.type == "text").strip()
