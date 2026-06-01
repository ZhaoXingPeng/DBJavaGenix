"""MCP v3 (2025-06-18 spec) sampling helper.

`sampling` is the *inverse* of regular tool calls: the server asks the client
to run an LLM inference on its behalf. The client decides whether to comply
(may prompt the user for approval) and uses its own LLM/budget.

Wire format:
```
{
  "method": "sampling/createMessage",
  "params": {
    "messages": [...],
    "systemPrompt": "...",
    "modelPreferences": {...},
    "maxTokens": 1024
  }
}
```

This module:
1. Builds the request payload (`build_sampling_request`)
2. Provides a thin Python adapter `SamplingClient` that mirrors a subset of
   the anthropic SDK surface so server-side code can swap between direct API
   calls and sampling with minimal changes.

Use case in DBJavaGenix:
- `ai_infer_business_names` would normally call Anthropic API directly
  (requires ANTHROPIC_API_KEY).
- With sampling, the same call goes to the client; CI/offline environments
  without an API key can still get LLM-enhanced inference via the client
  (which has its own model + budget).

Compatibility (2026-06):
- Claude Desktop 4.6+: full support
- Claude Code 2.x: full support
- Cherry Studio: not yet (planned)
- Cursor / Continue.dev: not yet
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ModelPreferences:
    """Soft preferences for which client model to use.

    The client is free to ignore these (e.g. force its own default).
    """

    intelligence_priority: float = 0.5
    speed_priority: float = 0.5
    cost_priority: float = 0.0
    hints: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "intelligencePriority": self.intelligence_priority,
            "speedPriority": self.speed_priority,
            "costPriority": self.cost_priority,
        }
        if self.hints:
            out["hints"] = [{"name": h} for h in self.hints]
        return out


def build_sampling_request(
    user_message: str,
    system_prompt: str | None = None,
    max_tokens: int = 1024,
    model_prefs: ModelPreferences | None = None,
) -> dict[str, Any]:
    """Build an MCP sampling/createMessage request payload.

    Args:
        user_message: the message the server wants the LLM to respond to
        system_prompt: optional system instruction
        max_tokens: max output tokens
        model_prefs: optional client-side model selection hints

    Returns:
        Dict ready to be sent as `params` of sampling/createMessage.
    """
    if not user_message:
        raise ValueError("user_message must be non-empty")
    if max_tokens <= 0 or max_tokens > 8192:
        raise ValueError("max_tokens out of range (1-8192)")

    payload: dict[str, Any] = {
        "messages": [
            {
                "role": "user",
                "content": {"type": "text", "text": user_message},
            }
        ],
        "maxTokens": max_tokens,
    }
    if system_prompt:
        payload["systemPrompt"] = system_prompt
    if model_prefs:
        payload["modelPreferences"] = model_prefs.to_dict()
    return payload


class SamplingClient:
    """A thin Python adapter that wraps a sampling-dispatch callable.

    The real MCP server transport injects the dispatcher (it knows how to
    serialize and forward to the client). This adapter lets server-side code
    write `client.complete(...)` the same way it would call the anthropic SDK,
    without depending on the actual transport.
    """

    def __init__(self, dispatcher):
        """Args:
        dispatcher: callable(payload_dict) -> response_dict, async or sync.
            Returns the response.content[0].text from the client's LLM.
        """
        if not callable(dispatcher):
            raise TypeError("dispatcher must be callable")
        self._dispatch = dispatcher

    async def complete(
        self,
        user_message: str,
        system_prompt: str | None = None,
        max_tokens: int = 1024,
        model_prefs: ModelPreferences | None = None,
    ) -> str:
        """Send a sampling request and return the text response."""
        payload = build_sampling_request(
            user_message=user_message,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            model_prefs=model_prefs,
        )
        result = self._dispatch(payload)
        if hasattr(result, "__await__"):
            result = await result
        return _extract_text(result)


def _extract_text(response: Any) -> str:
    """Pull the response text out of various plausible response shapes."""
    if response is None:
        return ""
    if isinstance(response, str):
        return response
    if isinstance(response, dict):
        content = response.get("content")
        if isinstance(content, list) and content:
            first = content[0]
            if isinstance(first, dict) and first.get("type") == "text":
                return str(first.get("text", ""))
        if "text" in response:
            return str(response["text"])
    return str(response)
