"""
Minimal client for OpenAI-compatible chat completion endpoints.

Works with OpenAI, Azure OpenAI (with an /v1-style proxy), Ollama, LM Studio,
vLLM, llama.cpp server, etc. Only enabled when ``llm_api_base_url`` is set.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:  # httpx is a core requirement, but keep the import guarded like other optional deps
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


class LLMClientError(RuntimeError):
    pass


class RemoteLLMClient:
    def __init__(self, base_url: str, api_key: Optional[str], model: str, timeout: float = 60.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self._client: Optional["httpx.AsyncClient"] = None

    @property
    def name(self) -> str:
        return f"remote:{self.model}"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _get_client(self) -> "httpx.AsyncClient":
        if httpx is None:
            raise LLMClientError("httpx is not installed")
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        client = self._get_client()
        url = f"{self.base_url}/chat/completions"
        try:
            response = await client.post(url, headers=self._headers(), json=payload)
            if response.status_code == 400 and json_mode:
                # Some servers reject response_format; retry without it.
                payload.pop("response_format", None)
                response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:300]
            raise LLMClientError(f"LLM endpoint returned {exc.response.status_code}: {detail}") from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"Could not reach LLM endpoint {url}: {exc}") from exc

        try:
            body = response.json()
            return body["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"Unexpected response from LLM endpoint: {response.text[:300]}") from exc


def extract_json_object(text: str) -> Dict[str, Any]:
    """
    Pull the first JSON object out of an LLM reply.

    Handles ```json fences, leading prose and trailing commentary.
    """
    if not text:
        raise ValueError("empty reply")
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    candidates = [fenced.group(1)] if fenced else []
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        candidates.append(text[start : end + 1])
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            continue
    raise ValueError("no JSON object found in reply")
