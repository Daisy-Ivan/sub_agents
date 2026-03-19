"""OpenAI-compatible LLM client for optional higher runtime modes."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from typing import Any, Callable, Mapping
from urllib import error, request

from .exceptions import LLMClientError

DEFAULT_LLM_BASE_URL = "http://127.0.0.1:8000/v1"
DEFAULT_LLM_MODEL = "Qwen/Qwen3.5-35B-A3B-FP8"


@dataclass(slots=True)
class LLMResponse:
    """Normalized response returned from the OpenAI-compatible client."""

    model: str
    content: str
    finish_reason: str | None = None
    usage: dict[str, Any] = field(default_factory=dict)
    raw_response: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable view of the response."""

        return {
            "model": self.model,
            "content": self.content,
            "finish_reason": self.finish_reason,
            "usage": dict(self.usage),
            "raw_response": dict(self.raw_response),
        }


class LLMClient:
    """Small OpenAI-compatible chat-completions client used for debugging."""

    def __init__(
        self,
        *,
        base_url: str = DEFAULT_LLM_BASE_URL,
        model: str = DEFAULT_LLM_MODEL,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        default_headers: Mapping[str, str] | None = None,
        default_request_options: Mapping[str, Any] | None = None,
        transport: Callable[..., Any] | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds
        self.default_headers = dict(default_headers or {})
        self.default_request_options = dict(default_request_options or {})
        self._transport = transport or request.urlopen

    @classmethod
    def from_options(cls, options: Mapping[str, Any] | None = None) -> "LLMClient":
        """Build a client from config-driven options."""

        resolved = dict(options or {})
        base_url = str(resolved.pop("base_url", DEFAULT_LLM_BASE_URL))
        model = str(resolved.pop("model", DEFAULT_LLM_MODEL))
        api_key_value = resolved.pop("api_key", None)
        api_key = str(api_key_value) if api_key_value not in (None, "") else None
        timeout_value = resolved.pop("timeout_seconds", resolved.pop("timeout", 60.0))
        try:
            timeout_seconds = float(timeout_value)
        except (TypeError, ValueError) as exc:
            raise LLMClientError("timeout_seconds must be numeric") from exc

        headers_value = resolved.pop("headers", {})
        if not isinstance(headers_value, Mapping):
            raise LLMClientError("llm header configuration must be a mapping")

        return cls(
            base_url=base_url,
            model=model,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
            default_headers={str(key): str(value) for key, value in headers_value.items()},
            default_request_options=resolved,
        )

    def chat(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        extra_options: Mapping[str, Any] | None = None,
    ) -> LLMResponse:
        """Call `/chat/completions` with an OpenAI-compatible payload."""

        if not messages:
            raise LLMClientError("chat requests require at least one message")

        payload: dict[str, Any] = {
            "model": model or self.model,
            "messages": [dict(message) for message in messages],
        }
        payload.update(self.default_request_options)
        if temperature is not None:
            payload["temperature"] = temperature
        if max_tokens is not None:
            payload["max_tokens"] = max_tokens
        if extra_options:
            payload.update(dict(extra_options))

        headers = {"Content-Type": "application/json", **self.default_headers}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        url = f"{self.base_url}/chat/completions"
        http_request = request.Request(
            url=url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            response = self._transport(http_request, timeout=self.timeout_seconds)
            response_body = response.read()
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise LLMClientError(
                f"chat completion request failed with HTTP {exc.code}: {body}"
            ) from exc
        except error.URLError as exc:
            raise LLMClientError(f"chat completion request failed: {exc.reason}") from exc
        except OSError as exc:
            raise LLMClientError(f"chat completion request failed: {exc}") from exc

        try:
            decoded = json.loads(response_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise LLMClientError("chat completion response was not valid JSON") from exc

        return LLMResponse(
            model=str(decoded.get("model") or payload["model"]),
            content=self._extract_content(decoded),
            finish_reason=self._extract_finish_reason(decoded),
            usage=self._extract_usage(decoded),
            raw_response=decoded,
        )

    def chat_completion(self, messages: list[dict[str, str]], **kwargs: Any) -> LLMResponse:
        """Alias that mirrors the remote API naming for debugging."""

        return self.chat(messages, **kwargs)

    def invoke(self, prompt: str, system_prompt: str | None = None, **kwargs: Any) -> str:
        """Convenience wrapper that sends a system/user message pair."""

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        return self.chat(messages, **kwargs).content

    def _extract_content(self, response_payload: Mapping[str, Any]) -> str:
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMClientError("chat completion response did not include choices")

        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            raise LLMClientError("chat completion choice payload is malformed")

        message = first_choice.get("message", {})
        if not isinstance(message, Mapping):
            raise LLMClientError("chat completion message payload is malformed")

        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, Mapping) and "text" in item:
                    parts.append(str(item["text"]))
            return "\n".join(part.strip() for part in parts if part.strip()).strip()
        raise LLMClientError("chat completion content had an unsupported shape")

    def _extract_finish_reason(self, response_payload: Mapping[str, Any]) -> str | None:
        choices = response_payload.get("choices")
        if not isinstance(choices, list) or not choices:
            return None
        first_choice = choices[0]
        if not isinstance(first_choice, Mapping):
            return None
        reason = first_choice.get("finish_reason")
        return str(reason) if reason is not None else None

    def _extract_usage(self, response_payload: Mapping[str, Any]) -> dict[str, Any]:
        usage = response_payload.get("usage", {})
        return dict(usage) if isinstance(usage, Mapping) else {}


__all__ = [
    "DEFAULT_LLM_BASE_URL",
    "DEFAULT_LLM_MODEL",
    "LLMClient",
    "LLMResponse",
]
