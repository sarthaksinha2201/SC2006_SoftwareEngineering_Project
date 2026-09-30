"""Adapter for the LLM used to extract events from post text (Anthropic Messages API).

The model is forced to answer through a single tool whose input schema is the event
schema, so its reply is structured data rather than prose. The reply is still treated as
untrusted: gowhere.ingest.extract validates every field before anything is stored.

Needs ANTHROPIC_API_KEY in .env. Without it, every call raises LlmError, and ingestion
stops without advancing any channel's last-processed marker.
"""
import os

from gowhere import config


class LlmError(Exception):
    """The call failed or returned nothing usable. The batch must be retried later."""


class LlmAdapter:
    def __init__(self, client=None, model=config.LLM_MODEL, max_tokens=4096, timeout_s=60):
        self._client = client
        self.model = model
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s

    def _get_client(self):
        if self._client is None:
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise LlmError("ANTHROPIC_API_KEY is not set")
            import anthropic
            self._client = anthropic.Anthropic(timeout=self.timeout_s, max_retries=2)
        return self._client

    def call_tool(self, system, user, tool):
        """The input the model passed to `tool` (a dict). Raises LlmError on any failure."""
        client = self._get_client()
        try:
            response = client.messages.create(
                model=self.model, max_tokens=self.max_tokens, system=system,
                messages=[{"role": "user", "content": user}],
                tools=[tool], tool_choice={"type": "tool", "name": tool["name"]})
        except Exception as e:     # the SDK's errors, timeouts and connection failures alike
            raise LlmError(f"{type(e).__name__}: {e}") from e
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise LlmError("reply was cut off at max_tokens")
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == tool["name"]:
                return block.input
        raise LlmError("reply contained no tool call")
