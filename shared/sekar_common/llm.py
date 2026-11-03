"""LLM clients: a local Ollama server, or any OpenAI-compatible API (OpenAI, OpenRouter, Groq, LM Studio...).
Claude lives in llm_anthropic.py (official Anthropic SDK). All clients share one small interface:

    .model, .label, .is_local, .models(), .chat(system, user, json_mode, max_tokens), .chat_json(...),
    .count_tokens(system, user) -> (tokens, exact), .usage (tokens used since the last reset_usage())
"""

import json
import re
import urllib.error
import urllib.request

DEFAULT_HOST = "http://localhost:11434"
PREFERRED_MODELS = ("qwen3", "qwen2.5", "llama3", "dolphin-llama3")
# Models that reason step by step before answering unless told not to; much slower and not needed here.
THINKING_MODELS = ("qwen3", "deepseek-r1")


class LLMError(Exception):
    pass


def parse_json(text):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    raise LLMError("The model returned an answer that was not valid JSON:\n" + text[:500])


def strip_thinking(text):
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


class BaseClient:
    is_local = False
    label = "AI"

    def __init__(self, model=None):
        self.model = model
        self.reset_usage()

    def reset_usage(self):
        self.usage = {"input": 0, "output": 0, "requests": 0}

    def _add_usage(self, inp, out):
        self.usage["input"] += inp or 0
        self.usage["output"] += out or 0
        self.usage["requests"] += 1

    def chat_json(self, system, user, timeout=600, max_tokens=None):
        return parse_json(self.chat(system, user, json_mode=True, timeout=timeout, max_tokens=max_tokens))

    def count_tokens(self, system, user):
        """Conservative estimate for providers without a counting endpoint. File paths and names tokenize
        worse than prose, so ~3 characters per token rather than the usual ~4."""
        return (len(system) + len(user)) // 3 + 10, False


def _http(url, payload=None, headers=None, timeout=10, what="the AI service"):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body)
            if isinstance(parsed, list) and parsed:   # Gemini sends [{"error": {...}}]
                parsed = parsed[0]
            detail = parsed.get("error", body) if isinstance(parsed, dict) else body
            detail = detail.get("message", detail) if isinstance(detail, dict) else detail
        except ValueError:
            detail = body
        hint = {401: " - check the API key", 403: " - the key isn't allowed to use this", 404: " - check the model name / URL",
                429: " - rate limited or out of credit"}.get(e.code, "")
        raise LLMError(f"{what} returned HTTP {e.code}{hint}: {str(detail)[:300]}") from e
    except OSError as e:
        raise LLMError(f"Cannot reach {what} ({e}).") from e


class Ollama(BaseClient):
    is_local = True

    def __init__(self, host=DEFAULT_HOST, model=None):
        super().__init__(model)
        self.host = (host or DEFAULT_HOST).rstrip("/")
        self.label = "Ollama (local)"

    def _request(self, path, payload=None, timeout=10):
        try:
            return _http(self.host + path, payload, timeout=timeout, what=f"Ollama at {self.host}")
        except LLMError as e:
            raise LLMError(f"{e} Is Ollama running?") from e

    def models(self):
        names = [m["name"] for m in self._request("/api/tags").get("models", [])]
        if names and self.model not in names:
            self.model = next((n for p in PREFERRED_MODELS for n in names if n.startswith(p)), names[0])
        return names

    def chat(self, system, user, json_mode=False, timeout=600, max_tokens=None):
        if not self.model:
            raise LLMError("No model selected.")
        payload = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 8192},
        }
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        if json_mode:
            payload["format"] = "json"
        if self.model.startswith(THINKING_MODELS):
            payload["think"] = False
        reply = self._request("/api/chat", payload, timeout=timeout)
        self._add_usage(reply.get("prompt_eval_count"), reply.get("eval_count"))
        return strip_thinking(reply.get("message", {}).get("content", ""))


# Models these services list that can't do text chat (embeddings, images, video, speech...).
NON_CHAT = re.compile(r"embed|imagen|veo|\btts\b|-tts|whisper|dall-e|moderation|\baqa\b|image-generation|"
                      r"transcribe|realtime|audio|lyria|-image\b|text-to-speech", re.I)
# Good everyday defaults, best first (fast, inexpensive, stable - previews and experiments last).
DEFAULT_PREFS = [r"^gemini-[\d.]+-flash$", r"^gemini-[\d.]+-flash", r"^gemini-.*flash", r"^gpt-[\w.]+-mini$",
                 r"^gpt-", r"^claude-", r"llama-?3", r"^mistral-(small|medium)", r"^deepseek-chat", r"qwen"]


def clean_model_id(model_id):
    """Gemini lists models as 'models/gemini-...'; the API accepts the bare name."""
    return model_id.split("/", 1)[1] if model_id.startswith("models/") else model_id


def _version(name):
    """'gemini-3.6-flash' -> (3, 6): newer versions sort higher (old ones get retired)."""
    m = re.search(r"(\d+(?:\.\d+)*)", name)
    return tuple(int(x) for x in m.group(1).split(".")) if m else ()


def pick_default(names):
    stable = [n for n in names if not re.search(r"preview|exp|beta|alpha|-\d{2}-\d{4}|lite|thinking", n, re.I)]
    for pattern in DEFAULT_PREFS:
        for pool in (stable, names):
            hits = [n for n in pool if re.search(pattern, n, re.I)]
            if hits:
                return max(hits, key=_version)    # the newest of the matching family
    return (stable or names)[0]


class OpenAICompatible(BaseClient):
    """Chat Completions API - works with OpenAI and the many services that copy its format."""

    def __init__(self, base_url, api_key, model=None, name=None, reasoning_effort=None):
        super().__init__(clean_model_id(model) if model else model)
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.label = name or self.base.split("//")[-1].split("/")[0]
        self.is_local = any(h in self.base for h in ("localhost", "127.0.0.1"))
        self._official = "api.openai.com" in self.base
        self.reasoning_effort = reasoning_effort    # "low" keeps thinking models (e.g. Gemini) from running for minutes

    def _headers(self):
        return {"Authorization": f"Bearer {self.key}"} if self.key else {}

    def models(self):
        data = _http(self.base + "/models", headers=self._headers(), timeout=15, what=self.label)
        names = sorted({clean_model_id(m["id"]) for m in data.get("data", []) if m.get("id")} - {""})
        chat = [n for n in names if not NON_CHAT.search(n)] or names
        if self.model:
            self.model = clean_model_id(self.model)
        if chat and self.model not in chat:
            self.model = pick_default(chat) if not self.model else self.model
        return chat

    def chat(self, system, user, json_mode=False, timeout=600, max_tokens=None):
        if not self.model:
            raise LLMError("No model selected - enter a model name in AI settings.")
        payload = {"model": self.model,
                   "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        if max_tokens:
            # OpenAI's newer models only accept max_completion_tokens; most compatible services use max_tokens.
            payload["max_completion_tokens" if self._official else "max_tokens"] = max_tokens
        if not self._official:
            payload["temperature"] = 0.2
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self.reasoning_effort:
            payload["reasoning_effort"] = self.reasoning_effort
        reply = _http(self.base + "/chat/completions", payload, headers=self._headers(), timeout=timeout, what=self.label)
        u = reply.get("usage") or {}
        self._add_usage(u.get("prompt_tokens"), u.get("completion_tokens"))
        choices = reply.get("choices") or [{}]
        return strip_thinking((choices[0].get("message") or {}).get("content", ""))
