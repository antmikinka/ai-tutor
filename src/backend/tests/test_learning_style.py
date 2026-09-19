"""VARK learning-style profile and its effect on practice generation."""

import asyncio

import pytest

from services import practice_service as ps
from services.learning_style import LearningStyle


def test_profile_from_screenshot_is_multimodal():
    # Visual 15, Aural 9, Read/write 15, Kinesthetic 12 (total 51 -> stepping distance 4)
    style = LearningStyle.from_mapping({"visual": 15, "aural": 9, "readWrite": 15, "kinesthetic": 12})
    assert style is not None and style.total == 51
    assert style.preferred() == ["visual", "read_write", "kinesthetic"]
    assert style.label() == "Multimodal (Visual, Read/write, Kinesthetic)"
    hint = style.prompt_hint()
    assert "sketch" in hint and "Kinesthetic" in hint and "Aural" not in hint
    assert style.to_dict()["label"].startswith("Multimodal")


def test_profile_edge_cases():
    assert LearningStyle.from_mapping(None) is None
    assert LearningStyle.from_mapping({}) is None
    assert LearningStyle.from_mapping({"visual": 0, "aural": 0}) is None
    single = LearningStyle.from_mapping({"aural": 12, "visual": 3, "read_write": 2, "kinesthetic": 1})
    assert single.preferred() == ["aural"] and single.label() == "Aural"
    clamped = LearningStyle.from_mapping({"visual": "99", "aural": "nonsense", "read_write": -4, "kinesthetic": 16})
    assert (clamped.visual, clamped.aural, clamped.read_write, clamped.kinesthetic) == (16, 0, 0, 16)
    everything = LearningStyle(10, 10, 10, 10)
    assert everything.label() == "Multimodal (VARK)" and len(everything.preferred()) == 4


def test_template_problem_carries_family_sketch_and_style(settings):
    svc = ps.PracticeService(settings, knowledge=None, ai=None)
    problem = asyncio.run(svc.generate("speed", "easy", seed=3, learning_style={"visual": 15, "aural": 9, "read_write": 15, "kinesthetic": 12}))
    assert problem["family"] == "motion"
    assert "distance-time graph" in problem["sketch"]
    assert problem["learning_style"]["label"].startswith("Multimodal")
    solution = svc.solution(problem["id"])
    assert solution["sketch"] == problem["sketch"]

    plain = asyncio.run(svc.generate("speed", "easy", seed=3))
    assert plain["learning_style"] is None and plain["sketch"]  # sketches are always offered; style is optional


def test_llm_prompt_includes_style_and_uses_model_sketch(settings):
    seen = {}

    class FakeAI:
        any_llm_available = True
        llm_name = "fake:llm"

        async def complete_json(self, system, user, **_):
            seen["user"] = user
            return {
                "problem": "A gym charges $25 to join plus $12 a month; after paying $121 in total, how many months has Priya been a member?",
                "equation": "25 + 12*m = 121",
                "variable": "m",
                "answer": "8",
                "concept": "fixed cost plus rate",
                "hints": ["Try m = 5 and see what the total would be.", "Subtract the joining fee first.", "25 + 12*m = 121"],
                "sketch": "Draw a bar for $121 split into a $25 block and equal $12 blocks.",
            }

    svc = ps.PracticeService(settings, knowledge=None, ai=FakeAI())
    problem = asyncio.run(svc.generate("gym", "medium", learning_style={"visual": 15, "aural": 9, "read_write": 15, "kinesthetic": 12}))
    assert "VARK profile prefers: Visual, Read/write, Kinesthetic" in seen["user"]
    assert problem["generator"] == "fake:llm"
    assert problem["sketch"].startswith("Draw a bar for $121")


def test_api_accepts_learning_style(client):
    body = client.post("/api/practice/generate", json={"topic": "discount", "mode": "templates", "learning_style": {"visual": 15, "aural": 9, "read_write": 15, "kinesthetic": 12}}).json()
    assert body["learning_style"]["preferred"] == ["visual", "read_write", "kinesthetic"]
    assert body["sketch"]
    assert client.post("/api/practice/generate", json={"topic": "x", "learning_style": {"visual": 40}}).status_code == 422
