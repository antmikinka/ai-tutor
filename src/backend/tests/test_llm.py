"""Remote LLM client plumbing, the runtime provider config, and the AIService gateway."""

import asyncio
import json

import pytest

from config.settings import create_settings
from services import llm_client
from services.ai_service import AIService, NoLanguageModelError
from services.llm_config import LLMConfigStore, mask_key


@pytest.fixture
def isolated_settings(settings, tmp_path):
    """Per-test data_dir so the persisted llm_config.json never leaks between tests."""
    def make(**overrides):
        s = create_settings(**{**settings.model_dump(), "data_dir": tmp_path / "data", **overrides})
        s.ensure_directories()
        return s

    return make


def test_extract_json_object_handles_fences_and_prose():
    assert llm_client.extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm_client.extract_json_object('Sure! Here it is: {"a": {"b": [1, 2]}} hope that helps') == {"a": {"b": [1, 2]}}
    with pytest.raises(ValueError):
        llm_client.extract_json_object("no json here")
    with pytest.raises(ValueError):
        llm_client.extract_json_object("")


# --------------------------------------------------------------------------- #
# Config store
# --------------------------------------------------------------------------- #


def test_config_store_defaults_and_openrouter_env(isolated_settings):
    store = LLMConfigStore(isolated_settings())
    assert store.config.mode == "auto"
    assert store.config.remote.preset == "openrouter"
    assert store.config.remote.configured is False  # no model / key yet

    s = isolated_settings(openrouter_api_key="sk-or-v1-abcdefgh12345678")
    store = LLMConfigStore(s)
    r = store.config.remote
    assert r.preset == "openrouter" and r.base_url == "https://openrouter.ai/api/v1"
    assert r.model == "openai/gpt-4o-mini" and r.configured
    public = store.public()
    assert public["remote"]["has_api_key"] is True
    assert "abcdefgh" not in json.dumps(public)  # key never leaves the process
    assert public["remote"]["api_key_hint"] == "sk-o…5678"


def test_config_store_env_base_url_detects_preset(isolated_settings):
    s = isolated_settings(llm_api_base_url="http://localhost:11434/v1/", llm_api_model="llama3.1")
    store = LLMConfigStore(s)
    assert store.config.remote.preset == "ollama"
    assert store.config.remote.base_url == "http://localhost:11434/v1"


def test_config_store_update_persists_and_overrides_env(isolated_settings):
    s = isolated_settings(llm_api_base_url="https://api.openai.com/v1", llm_api_key="env-key", llm_api_model="gpt-4o-mini")
    store = LLMConfigStore(s)
    store.update(mode="remote", preset="openrouter", api_key="sk-or-user", model="deepseek/deepseek-r1")
    assert store.path.exists()

    reloaded = LLMConfigStore(s)
    assert reloaded.config.mode == "remote"
    assert reloaded.config.remote.preset == "openrouter"
    assert reloaded.config.remote.base_url == "https://openrouter.ai/api/v1"
    assert reloaded.config.remote.api_key == "sk-or-user"
    assert reloaded.config.remote.model == "deepseek/deepseek-r1"

    # Switching preset without a model takes the preset default; clearing the key works.
    reloaded.update(preset="ollama", clear_api_key=True)
    assert reloaded.config.remote.model == "llama3.1" and reloaded.config.remote.api_key is None

    # Custom URL that matches no preset flips to "custom"; bad values are rejected.
    reloaded.update(base_url="http://192.168.1.5:8080/v1")
    assert reloaded.config.remote.preset == "custom"
    with pytest.raises(ValueError):
        reloaded.update(mode="sometimes")
    with pytest.raises(ValueError):
        reloaded.update(base_url="ftp://nope")
    with pytest.raises(ValueError):
        reloaded.update(preset="skynet")

    reloaded.reset()
    assert not reloaded.path.exists()
    assert reloaded.config.remote.preset == "openai" and reloaded.config.remote.api_key == "env-key"


def test_mask_key():
    assert mask_key(None) is None
    assert mask_key("short") == "•••••"
    assert mask_key("sk-or-v1-0123456789") == "sk-o…6789"


# --------------------------------------------------------------------------- #
# AIService routing
# --------------------------------------------------------------------------- #


def test_ai_service_without_any_llm_raises(isolated_settings):
    ai = AIService(isolated_settings())
    asyncio.run(ai.initialize())
    assert ai.any_llm_available is False and ai.llm_name is None and ai.active_backend() is None
    with pytest.raises(NoLanguageModelError):
        asyncio.run(ai.complete("sys", "user"))
    status = ai.status()
    assert status["llm_available"] is False and status["remote_llm"] is None and status["llm_mode"] == "auto"


def test_ai_service_remote_llm_word_problem(isolated_settings, monkeypatch):
    s = isolated_settings(llm_api_base_url="http://llm.local/v1/", llm_api_model="test-model")
    assert s.llm_api_base_url == "http://llm.local/v1"
    ai = AIService(s)
    asyncio.run(ai.initialize())
    assert ai.any_llm_available and ai.llm_name == "custom:test-model"

    async def fake_chat(messages, **kwargs):
        assert kwargs["json_mode"] is True
        return '{"equation": "3*x + 5 = 20", "variable": "x", "solution": "x = 4", "steps": ["set up"], "problem_type": "word_problem", "confidence": 0.7}'

    monkeypatch.setattr(ai.remote_llm, "chat", fake_chat)
    result = asyncio.run(ai.solve_math_problem("Three times a number plus five is twenty. What is the number?"))
    # The LLM's answer (4) is wrong; the engine corrects it to 5.
    assert result["model_used"] == "custom:test-model"
    assert result["solution"] == "x = 5"
    assert result["verification"]["method"] == "symbolic-corrected"
    assert result["steps"][0].startswith("Model the problem: 3*x + 5 = 20")
    assert result["confidence"] >= 0.85


def test_ai_service_remote_llm_failure_is_honest(isolated_settings, monkeypatch):
    ai = AIService(isolated_settings(llm_api_base_url="http://llm.local/v1"))
    asyncio.run(ai.initialize())

    async def failing_chat(messages, **kwargs):
        raise llm_client.LLMClientError("connection refused")

    monkeypatch.setattr(ai.remote_llm, "chat", failing_chat)
    result = asyncio.run(ai.solve_math_problem("a riddle about trains"))
    assert result["confidence"] == 0.0 and result["model_used"] == "none"
    assert any("language model error" in step for step in result["steps"])


def test_ai_service_mode_switching_at_runtime(isolated_settings):
    ai = AIService(isolated_settings(openrouter_api_key="sk-or-test"))
    asyncio.run(ai.initialize())
    assert ai.active_backend() == "remote" and ai.llm_name == "openrouter:openai/gpt-4o-mini"

    # "local only" with no local model loaded -> nothing available, message says why.
    status = asyncio.run(ai.apply_llm_config(mode="local"))
    assert status["mode"] == "local" and status["active"]["backend"] is None
    assert ai.any_llm_available is False
    with pytest.raises(NoLanguageModelError, match="local only"):
        asyncio.run(ai.complete("s", "u"))
    unsolved = asyncio.run(ai.solve_math_problem("some prose the engine cannot parse"))
    assert unsolved["model_used"] == "none" and any("local only" in step for step in unsolved["steps"])

    # Back to remote with a different model: the client is rebuilt, the old one is closed.
    old_client = ai.remote_llm
    status = asyncio.run(ai.apply_llm_config(mode="remote", model="qwen/qwq-32b"))
    assert ai.remote_llm is not old_client
    assert status["active"] == {"backend": "remote", "name": "openrouter:qwen/qwq-32b"}
    assert ai.remote_llm._headers()["HTTP-Referer"].startswith("https://")
    assert ai.remote_llm._headers()["Authorization"] == "Bearer sk-or-test"

    # Remote mode but nothing configured -> honest message about the API.
    asyncio.run(ai.apply_llm_config(preset="custom"))
    assert ai.remote_llm is None
    with pytest.raises(NoLanguageModelError, match="API"):
        asyncio.run(ai.complete("s", "u"))
    asyncio.run(ai.cleanup())


# --------------------------------------------------------------------------- #
# HTTP client
# --------------------------------------------------------------------------- #


def test_remote_client_http_errors(monkeypatch):
    httpx = pytest.importorskip("httpx")
    client = llm_client.RemoteLLMClient("http://llm.local/v1", "key", "m", timeout=1.0)
    assert client.provider == "custom" and client.name == "custom:m"

    def handler(request):
        assert request.headers["authorization"] == "Bearer key"
        if request.url.path.endswith("/chat/completions"):
            return httpx.Response(500, text="boom")
        return httpx.Response(404)

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(llm_client.LLMClientError, match="500"):
        asyncio.run(client.chat([{"role": "user", "content": "hi"}]))

    def ok_handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "hello"}}]})

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(ok_handler))
    assert asyncio.run(client.chat([{"role": "user", "content": "hi"}])) == "hello"
    asyncio.run(client.close())


def test_remote_client_openrouter_specifics():
    httpx = pytest.importorskip("httpx")
    client = llm_client.RemoteLLMClient("https://openrouter.ai/api/v1", "sk-or-x", "openai/gpt-4o-mini", timeout=1.0)
    assert client.provider == "openrouter"
    seen = {}

    def handler(request):
        seen["headers"] = dict(request.headers)
        if request.url.path.endswith("/models"):
            return httpx.Response(
                200,
                json={
                    "data": [
                        {"id": "zeta/cheap:free", "name": "Zeta", "context_length": 8000, "pricing": {"prompt": "0", "completion": "0"}},
                        {"id": "openai/gpt-4o-mini", "name": "GPT-4o mini", "context_length": 128000, "pricing": {"prompt": "0.00000015", "completion": "0.0000006"}},
                        {"id": "acme/model", "pricing": {"prompt": "0.000001", "completion": "0.000002"}, "supported_parameters": ["temperature", "response_format"], "architecture": {"input_modalities": ["text", "image"], "output_modalities": ["text"]}},
                        {"id": "music/gen", "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"input_modalities": ["text"], "output_modalities": ["text", "audio"]}},
                        {"id": "pix/gen", "pricing": {"prompt": "0", "completion": "0"}, "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]}},
                        {"not": "a model"},
                    ]
                },
            )
        if request.url.path.endswith("/chat/completions"):
            body = json.loads(request.content)
            if body.get("response_format"):
                return httpx.Response(400, json={"error": {"message": "response_format unsupported"}})
            return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})
        return httpx.Response(404)

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))

    models = asyncio.run(client.list_models())
    assert [m["id"] for m in models] == ["openai/gpt-4o-mini", "acme/model", "zeta/cheap:free"]  # recommended first, then alpha
    assert models[0]["recommended"] is True and models[0]["free"] is False
    assert models[2]["free"] is True and models[2]["context_length"] == 8000
    assert models[1]["json_mode"] is True and models[1]["vision"] is True and models[0]["json_mode"] is None
    assert seen["headers"]["x-title"] == "AI Math Tutor" and seen["headers"]["authorization"] == "Bearer sk-or-x"
    assert asyncio.run(client.list_models()) is models  # cached

    # json_mode: 400 on response_format -> transparent retry without it.
    assert asyncio.run(client.chat([{"role": "user", "content": "hi"}], json_mode=True)) == "OK"

    result = asyncio.run(client.test())
    assert result["ok"] is True and result["reply"] == "OK" and result["provider"] == "openrouter"

    def unauthorized(request):
        return httpx.Response(401, json={"error": {"message": "No auth credentials found"}})

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(unauthorized))
    result = asyncio.run(client.test())
    assert result["ok"] is False and "Authentication failed" in result["error"] and "No auth credentials" in result["error"]
    asyncio.run(client.close())


def test_remote_client_error_envelope_with_200():
    httpx = pytest.importorskip("httpx")
    client = llm_client.RemoteLLMClient("https://openrouter.ai/api/v1", "k", "m", timeout=1.0)

    def handler(request):
        return httpx.Response(200, json={"error": {"message": "Provider returned error", "code": 502}})

    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    with pytest.raises(llm_client.LLMClientError, match="Provider returned error"):
        asyncio.run(client.chat([{"role": "user", "content": "hi"}]))


# --------------------------------------------------------------------------- #
# REST API
# --------------------------------------------------------------------------- #


def test_llm_api_config_roundtrip(client, monkeypatch):
    body = client.get("/api/llm/config").json()
    assert body["mode"] == "auto" and {p["id"] for p in body["presets"]} >= {"openrouter", "openai", "ollama", "lmstudio", "custom"}
    assert body["remote"]["has_api_key"] is False

    resp = client.put("/api/llm/config", json={"mode": "remote", "preset": "openrouter", "api_key": "sk-or-v1-secretsecret", "model": "openai/gpt-4o-mini"})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["mode"] == "remote"
    assert body["remote"]["has_api_key"] is True and "secretsecret" not in resp.text
    assert body["active"] == {"backend": "remote", "name": "openrouter:openai/gpt-4o-mini"}

    # Capabilities and practice status reflect the change immediately.
    assert client.get("/api/practice/status").json()["llm"] == "openrouter:openai/gpt-4o-mini"
    assert client.get("/api/system/status").json()["services"]["ai_service"]["llm_active"] == "openrouter:openai/gpt-4o-mini"

    # Validation errors are 400s, not 500s.
    assert client.put("/api/llm/config", json={"base_url": "not-a-url"}).status_code == 400
    assert client.put("/api/llm/config", json={"preset": "skynet"}).status_code == 400
    assert client.put("/api/llm/config", json={"mode": "maybe"}).status_code == 422

    # Model listing and test go through the (mocked) provider.
    from api.dependencies import get_container
    from services import llm_client as lc

    httpx = pytest.importorskip("httpx")

    def handler(request):
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "openai/gpt-4o-mini", "name": "GPT-4o mini"}, {"id": "b/model"}]})
        return httpx.Response(200, json={"choices": [{"message": {"content": "OK"}}]})

    real_get_client = lc.RemoteLLMClient._get_client

    def fake_get_client(self):
        if self._client is None:
            self._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        return self._client

    monkeypatch.setattr(lc.RemoteLLMClient, "_get_client", fake_get_client)
    ai = get_container().ai_service
    ai.remote_llm._client = None  # drop any real client created before the patch

    listing = client.get("/api/llm/models").json()
    assert listing["provider"] == "openrouter" and listing["count"] == 2 and listing["models"][0]["id"] == "openai/gpt-4o-mini"
    # Listing for an unsaved provider (form values) works too and does not touch the saved config.
    proposed = client.post("/api/llm/models", json={"preset": "ollama"}).json()
    assert proposed["provider"] == "ollama" and proposed["base_url"] == "http://localhost:11434/v1" and proposed["count"] == 2
    assert client.get("/api/llm/config").json()["remote"]["preset"] == "openrouter"
    assert client.post("/api/llm/models", json={"preset": "custom", "base_url": ""}).status_code == 400

    tested = client.post("/api/llm/test", json={"model": "b/model"}).json()
    assert tested["ok"] is True and tested["model"] == "b/model" and tested["provider"] == "openrouter"
    assert client.post("/api/llm/test", json={"model": ""}).json()["ok"] is False

    monkeypatch.setattr(lc.RemoteLLMClient, "_get_client", real_get_client)

    # Reset returns to environment defaults (nothing configured in tests).
    body = client.delete("/api/llm/config").json()
    assert body["mode"] == "auto" and body["remote"]["has_api_key"] is False and body["active"]["backend"] is None
