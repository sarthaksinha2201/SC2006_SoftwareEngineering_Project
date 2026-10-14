"""Adapter for the LLM used to extract events from post text (OpenAI Responses API).

The model answers through Structured Outputs: the tool's input schema is sent as a
strict JSON schema, so the API itself refuses to return anything that does not fit it.
The reply is still treated as untrusted: gowhere.ingest.extract validates every field
before anything is stored, which is also the defence against a post that talks the
model into inventing a value.

Needs OPENAI_API_KEY in .env. Without it, every call raises LlmError, and ingestion
stops without advancing any channel's last-processed marker. The key never appears in
an error or a log line: error text is scrubbed of it before it leaves this module.
"""
import json
import logging
import os
import re
import threading

from gowhere import config

log = logging.getLogger(__name__)

# US$ per million tokens: (input, cached input, cache write, output), from
# developers.openai.com/api/docs/models/gpt-6-luna, read 14 Oct 2026.
PRICES_PER_M = {"gpt-6-luna": (0.10, 0.01, 0.125, 0.50)}
_KEY_LIKE = re.compile(r"sk-[A-Za-z0-9_\-*.]{6,}")


class LlmError(Exception):
    """The call failed or returned nothing usable. The batch must be retried later."""


def scrub(text, key=None):
    """`text` without the API key or anything shaped like one."""
    if key:
        text = text.replace(key, "[redacted]")
    return _KEY_LIKE.sub("[redacted]", text)


class LlmAdapter:
    def __init__(self, client=None, model=config.LLM_MODEL,
                 reasoning_effort=config.LLM_REASONING_EFFORT,
                 max_output_tokens=16000, timeout_s=120):
        self._client = client
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.max_output_tokens = max_output_tokens
        self.timeout_s = timeout_s
        self.usage = {"calls": 0, "input_tokens": 0, "cached_input_tokens": 0,
                      "cache_write_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0}
        self._lock = threading.Lock()

    def _get_client(self):
        if self._client is None:
            if not os.getenv("OPENAI_API_KEY"):
                raise LlmError("OPENAI_API_KEY is not set")
            import openai
            self._client = openai.OpenAI(timeout=self.timeout_s, max_retries=2)
        return self._client

    def call_tool(self, system, user, tool):
        """The structured reply matching tool["input_schema"] (a dict). Raises LlmError
        on any failure."""
        client = self._get_client()
        try:
            response = client.responses.create(
                model=self.model, instructions=system, input=user,
                max_output_tokens=self.max_output_tokens,
                reasoning={"effort": self.reasoning_effort},
                store=False,               # OpenAI keeps no copy of the posts
                text={"format": {"type": "json_schema", "name": tool["name"],
                                 "description": tool["description"],
                                 "schema": tool["input_schema"], "strict": True}})
        except Exception as e:     # the SDK's errors, timeouts and connection failures alike
            # `from None`: the SDK exception may carry the request, and so the key header
            raise LlmError(scrub(f"{type(e).__name__}: {e}", os.getenv("OPENAI_API_KEY"))) from None
        self._count(getattr(response, "usage", None))
        if getattr(response, "status", None) == "incomplete":
            reason = getattr(getattr(response, "incomplete_details", None), "reason", None)
            raise LlmError(f"reply was cut off ({reason})")
        text = None
        for item in getattr(response, "output", None) or []:
            if getattr(item, "type", None) != "message":
                continue                    # reasoning items carry no answer
            for part in item.content:
                if part.type == "refusal":
                    raise LlmError("the model refused the batch")
                if part.type == "output_text":
                    text = part.text
        if text is None:
            raise LlmError("reply contained no structured output")
        try:
            reply = json.loads(text)
        except ValueError:
            raise LlmError("reply was not valid JSON") from None
        if not isinstance(reply, dict):
            raise LlmError("reply was not a JSON object")
        return reply

    def _count(self, usage):
        if usage is None:
            return
        cached = getattr(getattr(usage, "input_tokens_details", None), "cached_tokens", 0) or 0
        written = getattr(getattr(usage, "input_tokens_details", None), "cache_write_tokens", 0) or 0
        reasoning = getattr(getattr(usage, "output_tokens_details", None), "reasoning_tokens", 0) or 0
        with self._lock:
            u = self.usage
            u["calls"] += 1
            u["input_tokens"] += usage.input_tokens
            u["cached_input_tokens"] += cached
            u["cache_write_tokens"] += written
            u["output_tokens"] += usage.output_tokens
            u["reasoning_tokens"] += reasoning
        log.info("LLM call: %d input tokens (%d cached), %d output (%d reasoning)",
                 usage.input_tokens, cached, usage.output_tokens, reasoning)

    def cost_usd(self):
        """What the calls so far cost at list price. Input tokens include cached and
        cache-write tokens; output tokens include reasoning tokens."""
        price_in, price_cached, price_write, price_out = PRICES_PER_M[self.model]
        u = self.usage
        plain = u["input_tokens"] - u["cached_input_tokens"] - u["cache_write_tokens"]
        return (plain * price_in + u["cached_input_tokens"] * price_cached
                + u["cache_write_tokens"] * price_write
                + u["output_tokens"] * price_out) / 1_000_000


class ReplayLlm:
    """Stands in for LlmAdapter without calling any model: answers each batch from
    {post_id: [events]}, numbering events by their post's position in the batch, as the
    model does. For tests and for rehearsing without OPENAI_API_KEY
    (python -m gowhere.ingest.run --replay-replies FILE). The replies in
    tests/fixtures/lepak/extractions.json are hand-written, not model output.
    Records every prompt; `fail_on` post ids make the whole call fail like an outage."""

    def __init__(self, replies, fail_on=()):
        self.replies, self.fail_on, self.calls = replies, set(fail_on), []

    def call_tool(self, system, user, tool):
        self.calls.append({"system": system, "user": user, "tool": tool})
        ids = re.findall(r'<post number="(\d+)" id="([^"]+)"', user)
        if self.fail_on & {pid for _, pid in ids}:
            raise LlmError("simulated outage")
        return {"events": [{"post": int(n), **e} for n, pid in ids
                           for e in self.replies.get(pid, [])]}
