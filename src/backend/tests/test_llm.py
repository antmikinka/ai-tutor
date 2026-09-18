"""Remote LLM client plumbing and the AIService gateway."""

import asyncio

import pytest

from services import llm_client
from services.ai_service import AIService, NoLanguageModelError


def test_extract_json_object_handles_fences_and_prose():
    assert llm_client.extract_json_object('```json\n{"a": 1}\n```') == {"a": 1}
    assert llm_client.extract_json_object('Sure! Here it is: {"a": {"b": [1, 2]}} hope that helps') == {"a": {"b": [1, 2]}}
    with pytest.raises(ValueError):
        llm_client.extract_json_object("no json here")
    with pytest.raises(ValueError):
        llm_client.extract_json_object("")


def test_ai_service_without_any_llm_raises(settings):
    ai = AIService(settings)
    asyncio.run(ai.initialize())
    assert ai.any_llm_available is False and ai.llm_name is None
    with pytest.raises(NoLanguageModelError):
        asyncio.run(ai.complete("sys", "user"))
    status = ai.status()
    assert status["llm_available"] is False and status["remote_llm"] is None


def test_ai_service_remote_llm_word_problem(settings, monkeypatch):
    from config.settings import create_settings

    s = create_settings(**{**settings.model_dump(), "llm_api_base_url": "http://llm.local/v1/", "llm_api_model": "test-model"})
    assert s.llm_api_base_url == "http://llm.local/v1"
    ai = AIService(s)
    asyncio.run(ai.initialize())
    assert ai.any_llm_available and ai.llm_name == "remote:test-model"

    async def fake_chat(messages, **kwargs):
        assert kwargs["json_mode"] is True
        return '{"equation": "3*x + 5 = 20", "variable": "x", "solution": "x = 4", "steps": ["set up"], "problem_type": "word_problem", "confidence": 0.7}'

    monkeypatch.setattr(ai.remote_llm, "chat", fake_chat)
    result = asyncio.run(ai.solve_math_problem("Three times a number plus five is twenty. What is the number?"))
    # The LLM's answer (4) is wrong; the engine corrects it to 5.
    assert result["model_used"] == "remote:test-model"
    assert result["solution"] == "x = 5"
    assert result["verification"]["method"] == "symbolic-corrected"
    assert result["steps"][0].startswith("Model the problem: 3*x + 5 = 20")
    assert result["confidence"] >= 0.85


def test_ai_service_remote_llm_failure_is_honest(settings, monkeypatch):
    from config.settings import create_settings

    s = create_settings(**{**settings.model_dump(), "llm_api_base_url": "http://llm.local/v1"})
    ai = AIService(s)
    asyncio.run(ai.initialize())

    async def failing_chat(messages, **kwargs):
        raise llm_client.LLMClientError("connection refused")

    monkeypatch.setattr(ai.remote_llm, "chat", failing_chat)
    result = asyncio.run(ai.solve_math_problem("a riddle about trains"))
    assert result["confidence"] == 0.0 and result["model_used"] == "none"
    assert any("language model error" in step for step in result["steps"])


def test_remote_client_http_errors(monkeypatch):
    httpx = pytest.importorskip("httpx")
    client = llm_client.RemoteLLMClient("http://llm.local/v1", "key", "m", timeout=1.0)

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
