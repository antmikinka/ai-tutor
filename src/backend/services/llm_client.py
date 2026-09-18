"""
Client for OpenAI-compatible chat completion endpoints.

Works with OpenRouter, OpenAI, Ollama, LM Studio, vLLM, llama.cpp server and
anything else that speaks ``POST /chat/completions`` + ``GET /models``.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:  # httpx is a core requirement, but keep the import guarded like other optional deps
    import httpx
except ImportError:  # pragma: no cover
    httpx = None  # type: ignore[assignment]


class LLMClientError(RuntimeError):
    pass


# Known providers. ``base_url`` is a default the user can override; ``needs_key``
# only affects the UI (a local server may still require one).
PROVIDER_PRESETS: Dict[str, Dict[str, Any]] = {
    "openrouter": {
        "label": "OpenRouter",
        "base_url": "https://openrouter.ai/api/v1",
        "needs_key": True,
        "key_url": "https://openrouter.ai/keys",
        "default_model": "openai/gpt-4o-mini",
        "description": "One API key for hundreds of hosted models (OpenAI, Anthropic, Google, DeepSeek, Qwen, Llama, ...).",
        "local": False,
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "needs_key": True,
        "key_url": "https://platform.openai.com/api-keys",
        "default_model": "gpt-4o-mini",
        "description": "OpenAI's API directly.",
        "local": False,
    },
    "ollama": {
        "label": "Ollama (local)",
        "base_url": "http://localhost:11434/v1",
        "needs_key": False,
        "key_url": None,
        "default_model": "llama3.1",
        "description": "Models you have pulled with `ollama pull`, served on this machine.",
        "local": True,
    },
    "lmstudio": {
        "label": "LM Studio (local)",
        "base_url": "http://localhost:1234/v1",
        "needs_key": False,
        "key_url": None,
        "default_model": "",
        "description": "LM Studio's local server (Developer tab -> Start server).",
        "local": True,
    },
    "custom": {
        "label": "Custom OpenAI-compatible",
        "base_url": "",
        "needs_key": False,
        "key_url": None,
        "default_model": "",
        "description": "vLLM, llama.cpp server, Azure proxies, text-generation-webui, ...",
        "local": False,
    },
}

# OpenRouter asks for these so the app shows up correctly in their dashboard.
OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/antmikinka/ai-tutor",
    "X-Title": "AI Math Tutor",
}

# Curated OpenRouter models that do well on maths; flagged in the model list when present.
OPENROUTER_RECOMMENDED = (
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "openai/o3-mini",
    "anthropic/claude-3.5-sonnet",
    "anthropic/claude-3.7-sonnet",
    "google/gemini-2.0-flash-001",
    "google/gemini-flash-1.5",
    "deepseek/deepseek-r1",
    "deepseek/deepseek-chat",
    "qwen/qwen-2.5-72b-instruct",
    "qwen/qwq-32b",
    "meta-llama/llama-3.3-70b-instruct",
)


def preset_for_url(base_url: str) -> str:
    url = (base_url or "").rstrip("/")
    for pid, preset in PROVIDER_PRESETS.items():
        if preset["base_url"] and preset["base_url"].rstrip("/") == url:
            return pid
    return "custom"


class RemoteLLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: Optional[str],
        model: str,
        timeout: float = 60.0,
        provider: Optional[str] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key or None
        self.model = model
        self.timeout = timeout
        self.provider = provider or preset_for_url(self.base_url)
        self._client: Optional["httpx.AsyncClient"] = None
        self._models_cache: Optional[List[Dict[str, Any]]] = None
        self._models_cached_at = 0.0

    @property
    def name(self) -> str:
        return f"{self.provider}:{self.model}"

    def _headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        if self.provider == "openrouter":
            headers.update(OPENROUTER_HEADERS)
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

    @staticmethod
    def _describe_http_error(exc: "httpx.HTTPStatusError") -> str:
        status = exc.response.status_code
        detail = exc.response.text[:300]
        try:
            body = exc.response.json()
            detail = body.get("error", {}).get("message") or body.get("message") or detail
        except Exception:  # noqa: BLE001 - best effort
            pass
        if status == 401:
            return f"Authentication failed ({status}): check the API key. {detail}"
        if status == 402:
            return f"Payment required ({status}): the account has no credits. {detail}"
        if status == 404:
            return f"Not found ({status}): check the base URL and model name. {detail}"
        if status == 429:
            return f"Rate limited ({status}): {detail}"
        return f"LLM endpoint returned {status}: {detail}"

    async def chat(
        self,
        messages: List[Dict[str, str]],
        *,
        temperature: float = 0.7,
        max_tokens: int = 1024,
        json_mode: bool = False,
    ) -> str:
        if not self.model:
            raise LLMClientError("No model selected for the remote language model.")
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
                # Some servers/models reject response_format; retry without it.
                payload.pop("response_format", None)
                response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(self._describe_http_error(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"Could not reach LLM endpoint {url}: {exc}") from exc

        try:
            body = response.json()
            if "error" in body and not body.get("choices"):
                # OpenRouter can return 200 with an error envelope (e.g. provider outage).
                raise LLMClientError(f"LLM endpoint error: {body['error'].get('message', body['error'])}")
            return body["choices"][0]["message"]["content"] or ""
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(f"Unexpected response from LLM endpoint: {response.text[:300]}") from exc

    async def list_models(self, *, refresh: bool = False, cache_seconds: float = 600.0) -> List[Dict[str, Any]]:
        """Return ``[{id, name, context_length, prompt_price, completion_price, free, recommended}]``."""
        now = time.monotonic()
        if not refresh and self._models_cache is not None and now - self._models_cached_at < cache_seconds:
            return self._models_cache

        client = self._get_client()
        url = f"{self.base_url}/models"
        try:
            response = await client.get(url, headers=self._headers())
            response.raise_for_status()
            body = response.json()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(self._describe_http_error(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"Could not reach LLM endpoint {url}: {exc}") from exc
        except ValueError as exc:
            raise LLMClientError(f"Model list was not JSON: {exc}") from exc

        raw = body.get("data", body) if isinstance(body, dict) else body
        if not isinstance(raw, list):
            raise LLMClientError("Unexpected model list format")

        models: List[Dict[str, Any]] = []
        for item in raw:
            if not isinstance(item, dict) or not item.get("id"):
                continue
            pricing = item.get("pricing") or {}
            prompt_price = _price(pricing.get("prompt"))
            completion_price = _price(pricing.get("completion"))
            model_id = str(item["id"])
            models.append(
                {
                    "id": model_id,
                    "name": str(item.get("name") or model_id),
                    "context_length": item.get("context_length") or (item.get("top_provider") or {}).get("context_length"),
                    "prompt_price": prompt_price,
                    "completion_price": completion_price,
                    "free": (prompt_price == 0 and completion_price == 0) if pricing else None,
                    "recommended": self.provider == "openrouter" and model_id in OPENROUTER_RECOMMENDED,
                }
            )
        models.sort(key=lambda m: (not m["recommended"], m["id"].lower()))
        self._models_cache = models
        self._models_cached_at = now
        return models

    async def test(self) -> Dict[str, Any]:
        """Fire a one-token request so the UI can confirm URL, key and model together."""
        started = time.perf_counter()
        try:
            reply = await self.chat(
                [{"role": "user", "content": "Reply with the single word OK."}],
                temperature=0.0,
                max_tokens=8,
            )
        except LLMClientError as exc:
            return {"ok": False, "error": str(exc), "latency_ms": round((time.perf_counter() - started) * 1000), "model": self.model, "provider": self.provider}
        return {
            "ok": True,
            "error": None,
            "reply": reply.strip()[:80],
            "latency_ms": round((time.perf_counter() - started) * 1000),
            "model": self.model,
            "provider": self.provider,
        }


def _price(value: Any) -> Optional[float]:
    """OpenRouter reports USD per token as strings; other servers omit pricing."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
