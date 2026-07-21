"""Provider-agnostic LLM client: Groq (primary) + Gemini (fallback).

- Groq is called through its OpenAI-compatible REST API with plain `requests`
  (json_object mode; the JSON schema is embedded in the prompt because
  llama-3.3-70b-versatile supports json_mode but not strict structured_outputs).
- Gemini uses the google-genai SDK with response_mime_type=application/json.
- Both paths take the SAME standard JSON Schema (lowercase types) so callers
  never care which provider answered.
- Retries with exponential backoff on 429/5xx/timeouts, honoring Retry-After.
- If the primary provider is exhausted (e.g. daily quota), automatically falls
  back to the other provider when its key is configured.
- Counts every request per provider (read via .stats) for run metadata and
  quota warnings.

CLI self-test:  python llm_client.py
"""

import json
import os
import time

import requests
from dotenv import load_dotenv

from common import get_logger

load_dotenv()
log = get_logger("llm")

GROQ_BASE = "https://api.groq.com/openai/v1"
# Preference order when GROQ_MODEL is unset; verified against the live /models
# endpoint at startup so a deprecated ID can never be used silently.
GROQ_PREFERRED = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "llama-3.1-8b-instant"]

MAX_RETRIES = 5
TIMEOUT_S = 120


class LLMError(Exception):
    pass


class ProviderExhausted(LLMError):
    """Provider keeps 429ing / failing after all retries."""


def _backoff_sleep(attempt: int, retry_after: str | None = None) -> None:
    if retry_after:
        try:
            wait = min(float(retry_after) + 1, 120)
            log.info("Honoring Retry-After: sleeping %.0fs", wait)
            time.sleep(wait)
            return
        except ValueError:
            pass
    wait = min(2 ** attempt * 2, 60)  # 2,4,8,16,32,60...
    log.info("Backing off %.0fs (attempt %d/%d)", wait, attempt + 1, MAX_RETRIES)
    time.sleep(wait)


def _extract_json(text: str) -> dict | list:
    """Parse model output as JSON, tolerating markdown fences and prose wrap."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # last resort: grab the outermost {...} or [...]
        for open_c, close_c in [("{", "}"), ("[", "]")]:
            start, end = text.find(open_c), text.rfind(close_c)
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    continue
    raise LLMError(f"Model returned unparseable JSON: {text[:200]!r}")


class LLMClient:
    def __init__(self):
        self.provider = os.getenv("LLM_PROVIDER", "groq").lower()
        self.groq_key = os.getenv("GROQ_API_KEY", "")
        self.gemini_key = os.getenv("GEMINI_API_KEY", "")
        self.gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
        self.groq_model = os.getenv("GROQ_MODEL", "") or None  # resolved lazily
        self.stats = {"groq_requests": 0, "gemini_requests": 0, "retries": 0,
                      "fallbacks": 0, "groq_model": None, "gemini_model": self.gemini_model}
        self._gemini_client = None

    # ── Groq ────────────────────────────────────────────────────────

    def verify_groq_model(self) -> str:
        """Resolve + verify the Groq model ID against the LIVE /models endpoint."""
        if not self.groq_key:
            raise LLMError("GROQ_API_KEY not set")
        r = requests.get(f"{GROQ_BASE}/models",
                         headers={"Authorization": f"Bearer {self.groq_key}"},
                         timeout=30)
        r.raise_for_status()
        live = {m["id"]: m for m in r.json()["data"] if m.get("active")}
        if self.groq_model:
            if self.groq_model not in live:
                raise LLMError(f"GROQ_MODEL={self.groq_model!r} is not in the live "
                               f"model list. Active text models: "
                               f"{[m for m in live if 'json_mode' in (live[m].get('supported_features') or [])]}")
        else:
            for candidate in GROQ_PREFERRED:
                if candidate in live:
                    self.groq_model = candidate
                    break
            else:
                raise LLMError("None of the preferred Groq models are live; set GROQ_MODEL manually.")
        self.stats["groq_model"] = self.groq_model
        log.info("Groq model verified live: %s", self.groq_model)
        return self.groq_model

    def _groq_json(self, system: str, prompt: str, schema: dict, max_tokens: int) -> dict | list:
        if not self.groq_model:
            self.verify_groq_model()
        # json_object mode requires "JSON" in the messages; we embed the schema.
        sys_msg = (f"{system}\n\nRespond ONLY with JSON matching this JSON Schema "
                   f"exactly (no extra keys, no prose):\n{json.dumps(schema)}")
        body = {
            "model": self.groq_model,
            "messages": [{"role": "system", "content": sys_msg},
                         {"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                r = requests.post(f"{GROQ_BASE}/chat/completions",
                                  headers={"Authorization": f"Bearer {self.groq_key}"},
                                  json=body, timeout=TIMEOUT_S)
                self.stats["groq_requests"] += 1
                if r.status_code == 429 or r.status_code >= 500:
                    last_err = f"HTTP {r.status_code}: {r.text[:200]}"
                    # A DAILY cap (tokens/requests per day) won't clear by waiting —
                    # fail over to the other provider immediately instead of sleeping.
                    low = r.text.lower()
                    if "per day" in low or "tpd" in low or "rpd" in low:
                        log.warning("Groq DAILY limit reached — failing over now (no retry): %s",
                                    last_err)
                        raise ProviderExhausted(f"Groq daily limit: {last_err}")
                    log.warning("Groq %s", last_err)
                    self.stats["retries"] += 1
                    _backoff_sleep(attempt, r.headers.get("retry-after"))
                    continue
                r.raise_for_status()
                content = r.json()["choices"][0]["message"]["content"]
                return _extract_json(content)
            except (requests.Timeout, requests.ConnectionError) as e:
                last_err = repr(e)
                log.warning("Groq network error: %s", last_err)
                self.stats["retries"] += 1
                _backoff_sleep(attempt)
        raise ProviderExhausted(f"Groq failed after {MAX_RETRIES} attempts: {last_err}")

    # ── Gemini ──────────────────────────────────────────────────────

    def _gemini_json(self, system: str, prompt: str, schema: dict, max_tokens: int) -> dict | list:
        if not self.gemini_key:
            raise LLMError("GEMINI_API_KEY not set")
        if self._gemini_client is None:
            from google import genai  # imported lazily so Groq-only runs don't need it
            self._gemini_client = genai.Client(api_key=self.gemini_key)
        # Schema goes in the prompt (same as Groq) + JSON mime type enforced.
        full_prompt = (f"{system}\n\nRespond ONLY with JSON matching this JSON Schema "
                       f"exactly:\n{json.dumps(schema)}\n\n---\n\n{prompt}")
        # Gemini 3.x flash is a THINKING model: reasoning tokens are drawn from the
        # output budget, so a tight max_output_tokens truncates the JSON. Give
        # generous headroom (thinking + the actual answer both have to fit).
        out_budget = max(max_tokens * 2, 8192)
        last_err = None
        for attempt in range(MAX_RETRIES):
            try:
                r = self._gemini_client.models.generate_content(
                    model=self.gemini_model,
                    contents=full_prompt,
                    config={"response_mime_type": "application/json",
                            "temperature": 0.2,
                            "max_output_tokens": out_budget},
                )
                self.stats["gemini_requests"] += 1
                return _extract_json(r.text)
            except Exception as e:  # google-genai raises its own ClientError types
                self.stats["gemini_requests"] += 1
                msg = str(e)
                last_err = f"{type(e).__name__}: {msg[:200]}"
                transient = ("429" in msg or "RESOURCE_EXHAUSTED" in msg
                             or "500" in msg or "503" in msg or "UNAVAILABLE" in msg
                             or "Deadline" in msg)
                if not transient:
                    raise LLMError(f"Gemini non-retryable error: {last_err}") from e
                log.warning("Gemini %s", last_err)
                self.stats["retries"] += 1
                _backoff_sleep(attempt)
        raise ProviderExhausted(f"Gemini failed after {MAX_RETRIES} attempts: {last_err}")

    # ── Public API ──────────────────────────────────────────────────

    def generate_json(self, prompt: str, schema: dict, system: str = "You are a precise analyst.",
                      max_tokens: int = 4096) -> dict | list:
        """One structured-output call. Tries the configured provider, falls back
        to the other on exhaustion. Raises LLMError if both fail."""
        order = ["groq", "gemini"] if self.provider == "groq" else ["gemini", "groq"]
        errors = []
        for i, prov in enumerate(order):
            if prov == "groq" and not self.groq_key:
                continue
            if prov == "gemini" and not self.gemini_key:
                continue
            try:
                fn = self._groq_json if prov == "groq" else self._gemini_json
                return fn(system, prompt, schema, max_tokens)
            except ProviderExhausted as e:
                errors.append(str(e))
                if i + 1 < len(order):
                    self.stats["fallbacks"] += 1
                    log.warning("Provider %s exhausted — falling back to %s", prov, order[i + 1])
        raise LLMError("All providers failed: " + " | ".join(errors))


if __name__ == "__main__":
    # Self-test: verify Groq model live, then one structured call per provider.
    test_schema = {
        "type": "object",
        "properties": {
            "sentiment": {"type": "string", "enum": ["positive", "negative", "mixed", "neutral"]},
            "summary": {"type": "string"},
        },
        "required": ["sentiment", "summary"],
    }
    review = ("I only ever order milk and bread on Blinkit, never knew they even "
              "sold pet food until my friend told me.")

    client = LLMClient()
    print("Verified Groq model:", client.verify_groq_model())

    print("\n-- Groq structured call --")
    out = client._groq_json("Analyze this app review.", review, test_schema, 512)
    print(json.dumps(out, indent=2))

    print("\n-- Gemini structured call --")
    out = client._gemini_json("Analyze this app review.", review, test_schema, 512)
    print(json.dumps(out, indent=2))

    print("\nStats:", json.dumps(client.stats, indent=2))
