"""The LLM adapter (OpenAI Responses API with Structured Outputs), against a fake client.
Nothing here calls OpenAI."""
import logging
from types import SimpleNamespace

import pytest

from gowhere.adapters import llm
from gowhere.adapters.llm import LlmAdapter, LlmError, scrub
from gowhere.ingest.extract import TOOL

KEY = "sk-proj-TESTKEY0123456789abcdefABCDEF"


def usage(inp=1200, cached=200, out=300, reasoning=100):
    return SimpleNamespace(input_tokens=inp, output_tokens=out,
                           input_tokens_details=SimpleNamespace(cached_tokens=cached, cache_write_tokens=0),
                           output_tokens_details=SimpleNamespace(reasoning_tokens=reasoning))


def reply(text='{"events": []}', status="completed", parts=None, reason=None):
    parts = parts if parts is not None else [SimpleNamespace(type="output_text", text=text)]
    return SimpleNamespace(status=status, usage=usage(),
                           incomplete_details=SimpleNamespace(reason=reason) if reason else None,
                           output=[SimpleNamespace(type="reasoning", content=[]),
                                   SimpleNamespace(type="message", content=parts)])


class FakeClient:
    def __init__(self, response=None, raises=None):
        self.response, self.raises, self.kwargs = response, raises, None
        self.responses = self

    def create(self, **kwargs):
        self.kwargs = kwargs
        if self.raises:
            raise self.raises
        return self.response


def test_sends_the_schema_as_strict_structured_output_and_returns_the_reply():
    client = FakeClient(reply('{"events": [{"post": 1}]}'))
    assert LlmAdapter(client=client).call_tool("system", "user", TOOL) == {"events": [{"post": 1}]}
    k = client.kwargs
    assert k["model"] == "gpt-6-luna" and k["instructions"] == "system" and k["input"] == "user"
    assert k["text"]["format"] == {"type": "json_schema", "name": "record_events",
                                   "description": TOOL["description"],
                                   "schema": TOOL["input_schema"], "strict": True}
    assert k["store"] is False and k["reasoning"] == {"effort": "low"}


@pytest.mark.parametrize("client", [
    FakeClient(raises=TimeoutError("simulated")),
    FakeClient(reply("Sure! Here are the events...")),                         # not JSON
    FakeClient(reply('["not", "an", "object"]')),
    FakeClient(reply(parts=[SimpleNamespace(type="refusal", refusal="I can't help")])),
    FakeClient(reply(parts=[])),                                                # no answer
    FakeClient(reply('{"events": [', status="incomplete", reason="max_output_tokens")),
])
def test_failures_raise_llm_error(client):
    with pytest.raises(LlmError):
        LlmAdapter(client=client).call_tool("s", "u", TOOL)


def test_without_a_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(LlmError, match="OPENAI_API_KEY is not set"):
        LlmAdapter().call_tool("s", "u", TOOL)


class AuthenticationError(Exception):
    """Shaped like the SDK's: its message echoes the key it was given."""


def test_the_key_never_reaches_error_text_or_logs(monkeypatch, caplog):
    monkeypatch.setenv("OPENAI_API_KEY", KEY)
    leaky = AuthenticationError(f"Error code: 401 - Incorrect API key provided: {KEY}. "
                                f"Authorization: Bearer {KEY}")
    adapter = LlmAdapter(client=FakeClient(raises=leaky))
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(LlmError) as err:
            adapter.call_tool("s", "u", TOOL)
        logging.getLogger("gowhere.ingest.run").error("LLM call failed: %s", err.value)
    assert KEY not in str(err.value) and "[redacted]" in str(err.value)
    assert err.value.__cause__ is None and err.value.__suppress_context__   # no chained SDK error
    assert KEY not in caplog.text
    assert "TESTKEY" not in caplog.text


def test_scrub_catches_partly_masked_keys_too():
    assert scrub("Incorrect API key provided: sk-proj-****************cdef.") == \
        "Incorrect API key provided: [redacted]"
    assert scrub(f"x {KEY} y", KEY) == "x [redacted] y"


def test_usage_and_cost_are_totalled(caplog):
    adapter = LlmAdapter(client=FakeClient(reply()))
    with caplog.at_level(logging.INFO, logger="gowhere.adapters.llm"):
        adapter.call_tool("s", "u", TOOL)
        adapter.call_tool("s", "u", TOOL)
    assert adapter.usage == {"calls": 2, "input_tokens": 2400, "cached_input_tokens": 400,
                             "cache_write_tokens": 0, "output_tokens": 600, "reasoning_tokens": 200}
    # 2,000 plain input x $0.10 + 400 cached x $0.01 + 600 output x $0.50, per million
    assert adapter.cost_usd() == pytest.approx((2000 * 0.10 + 400 * 0.01 + 600 * 0.50) / 1e6)
    assert "1200 input tokens (200 cached), 300 output (100 reasoning)" in caplog.text


def test_every_price_is_known_for_the_configured_model():
    from gowhere import config
    assert config.LLM_MODEL in llm.PRICES_PER_M
