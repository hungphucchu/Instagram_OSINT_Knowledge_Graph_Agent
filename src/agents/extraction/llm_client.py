"""OpenAI-compatible LLM client wrapper for extraction."""

from __future__ import annotations

import logging
import time
from typing import Any


class LLMClient:
    """Thin wrapper around OpenAI-compatible chat completions API."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        timeout_seconds: int,
        max_retries: int = 0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds
        self._max_retries = max(0, max_retries)
        self._client = None
        self._log = logging.getLogger("extraction.llm_client")

    def generate_json(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> Any:
        """Generate one chat completion response object."""
        client = self._get_client()
        self._log.info(
            "llm_request_start model=%s timeout_seconds=%s messages=%s max_tokens=%s max_retries=%s",
            model,
            self._timeout_seconds,
            len(messages),
            max_tokens,
            self._max_retries,
        )
        started = time.monotonic()
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        response = client.chat.completions.create(**kwargs)
        elapsed_ms = int((time.monotonic() - started) * 1000)
        self._log.info("llm_request_done model=%s elapsed_ms=%s", model, elapsed_ms)
        return response

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ImportError(
                "openai package is required for EXTRACT_MODE=llm. Install with: python -m pip install openai"
            ) from exc
        self._client = OpenAI(
            base_url=self._base_url,
            api_key=self._api_key,
            timeout=self._timeout_seconds,
            max_retries=self._max_retries,
        )
        return self._client
