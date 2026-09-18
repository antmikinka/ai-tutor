"""Practice problems: template generation, engine validation, LLM path, checking, hints, API."""

import asyncio
import random

import pytest

from services import practice_service as ps
from services.ai_service import NoLanguageModelError


# --------------------------------------------------------------------------- #
# Templates
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("family,template", [(f, t) for f, spec in ps.FAMILIES.items() for t in spec["templates"]])
def test_every_template_is_engine_verified(family, template):
    for seed in range(15):
        g = template(random.Random(seed), "medium")
        ok, result, why = ps._engine_check(g.equation, g.answer)
        assert ok, f"{template.__name__} seed={seed}: {why}"
        assert g.problem and len(g.hints) == 3 and g.family == family
        assert result is not None


def test_pick_family_prefers_explicit_topic_over_material():
    rng = random.Random(0)
    material = "rate rate rate proportion recipe per per per ratio"  # noisy context
    assert ps.pick_family("rate of change velocity", material, "medium", rng) == "calculus"
    assert ps.pick_family("quadratic equations", "", "hard", rng) == "quadratic"
    assert ps.pick_family("percent discount", "", "easy", rng) == "percent"


def test_pick_family_uses_material_when_topic_is_vague():
    rng = random.Random(1)
    material = "Chapter 5: exponential growth and decay. Bacteria double every hour; half-life problems."
    assert ps.pick_family("practice", material, "medium", rng) == "exponential"


def test_pick_family_falls_back_by_difficulty():
    for difficulty in ps.DIFFICULTIES:
        fam = ps.pick_family("anything", "", difficulty, random.Random(3))
        assert fam in ps._DEFAULT_BY_DIFFICULTY[difficulty]


def test_generate_from_templates_honours_family_and_difficulty():
    g = ps.generate_from_templates("whatever", "hard", "", random.Random(2), family="calculus")
    assert g.family == "calculus"


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


class FakeAI:
    """Stand-in for AIService.complete_json."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = 0
        self.any_llm_available = True
        self.llm_name = "fake:llm"

    async def complete_json(self, system, user, **_):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def service(settings):
    svc = ps.PracticeService(settings, knowledge=None, ai=None)
    asyncio.run(svc.initialize())
    return svc


def test_generate_without_llm_or_material(service):
    problem = asyncio.run(service.generate("linear equations", "easy", seed=7))
    assert problem["family"] == "linear"
    assert problem["generator"] == "templates"
    assert problem["equation"] and problem["equation_latex"]
    assert problem["hints"] == [] and problem["hints_available"] == 3
    assert problem["sources"] == []
    assert "answer" not in problem  # never leak the answer in the public payload


def test_check_hint_solution_flow(service):
    problem = asyncio.run(service.generate("shopping", "easy", family="linear", seed=11))
    pid = problem["id"]
    stored = service.get(pid)

    wrong = service.check(pid, "123456")
    assert wrong["correct"] is False and wrong["attempts"] == 1 and wrong["hint"] is None

    wrong2 = service.check(pid, "654321")
    assert wrong2["correct"] is False and wrong2["hint"] == stored.hints[0] and wrong2["hints_used"] == 1

    unreadable = service.check(pid, "banana???")
    assert unreadable["correct"] is False and unreadable["unreadable"] is True
    assert unreadable["attempts"] == 2 and unreadable["hint"] is None  # typos cost nothing

    hint = service.hint(pid)
    assert hint["hints_used"] == 2 and hint["exhausted"] is False

    right = service.check(pid, f"{stored.variable} = {stored.answer}")
    assert right["correct"] is True and right["solved"] is True
    assert right["answer"] == stored.answer_display

    solution = service.solution(pid)
    assert solution["answer"] == stored.answer_display
    assert solution["steps"][0].startswith("Model the situation")
    assert solution["engine_solution"]

    stats = service.stats()
    assert stats["generated"] == 1 and stats["solved"] == 1 and stats["first_try"] == 0 and stats["attempts"] == 3


def test_check_rejects_extraneous_root(service):
    problem = asyncio.run(service.generate("projectile", "hard", family="quadratic", seed=5))
    stored = service.get(problem["id"])
    import sympy as sp

    from services import math_engine

    roots = math_engine.solve(stored.equation).result
    negative = next(r for r in roots if sp.simplify(r) != sp.sympify(stored.answer))
    verdict = service.check(problem["id"], str(negative))
    assert verdict["correct"] is False
    assert "does solve the equation" in verdict["feedback"]


def test_check_first_try_and_streak(service):
    for _ in range(2):
        problem = asyncio.run(service.generate("speed", "easy", family="motion"))
        stored = service.get(problem["id"])
        assert service.check(problem["id"], stored.answer)["correct"]
    stats = service.stats()
    assert stats["first_try"] == 2 and stats["streak"] == 2 and stats["best_streak"] == 2


def test_check_unknown_problem(service):
    with pytest.raises(KeyError):
        service.check("nope", "1")
    with pytest.raises(ValueError):
        problem = asyncio.run(service.generate("x", "easy"))
        service.check(problem["id"], "   ")


def test_generate_with_llm_validates_against_engine(settings):
    good = {
        "problem": "A taxi charges $3 plus $2 per km. A ride cost $17. How far was it?",
        "equation": "2*d + 3 = 17",
        "variable": "d",
        "answer": "7",
        "concept": "Linear model",
        "hints": ["Let d be km", "cost = 3 + 2d", "2d + 3 = 17"],
    }
    ai = FakeAI([good])
    svc = ps.PracticeService(settings, knowledge=None, ai=ai)
    problem = asyncio.run(svc.generate("taxi fares", "easy"))
    assert problem["generator"] == "fake:llm"
    assert problem["equation"] == "2*d + 3 = 17"
    assert problem["equation_latex"] == "2 d + 3 = 17"
    assert svc.check(problem["id"], "7")["correct"] is True


def test_generate_with_llm_retries_then_falls_back_to_templates(settings):
    wrong_answer = {"problem": "p", "equation": "2*d + 3 = 17", "answer": "8", "hints": []}
    unparsable = {"problem": "p", "equation": "the vibes", "answer": "1", "hints": []}
    ai = FakeAI([wrong_answer, unparsable])
    svc = ps.PracticeService(settings, knowledge=None, ai=ai)
    problem = asyncio.run(svc.generate("linear equations", "easy", seed=1))
    assert ai.calls == 2
    assert problem["generator"] == "templates"
    assert "could not be verified" in problem["note"]


def test_generate_with_llm_error_falls_back(settings):
    ai = FakeAI([NoLanguageModelError("endpoint down")])
    svc = ps.PracticeService(settings, knowledge=None, ai=ai)
    problem = asyncio.run(svc.generate("percent", "easy"))
    assert problem["generator"] == "templates" and problem["family"] == "percent"


def test_generate_grounded_in_knowledge(settings, tmp_path):
    from config.settings import create_settings
    from services.knowledge_service import KnowledgeService

    s = create_settings(**{**settings.model_dump(), "knowledge_dir": tmp_path / "kb", "knowledge_embedding": "hashing"})
    kb = KnowledgeService(s)
    asyncio.run(kb.initialize())
    kb.add_text("Unit 7", "Exponential growth: a population that doubles every hour follows N = N0 * 2^t.")
    svc = ps.PracticeService(s, knowledge=kb, ai=None)
    problem = asyncio.run(svc.generate("practice from my notes", "medium", seed=4))
    assert problem["family"] == "exponential"
    assert problem["sources"] and problem["sources"][0]["title"] == "Unit 7"
    assert "Unit 7" in problem["note"]


# --------------------------------------------------------------------------- #
# API
# --------------------------------------------------------------------------- #


def test_practice_api_flow(client):
    status = client.get("/api/practice/status").json()
    assert status["difficulties"] == ["easy", "medium", "hard"]
    assert any(f["id"] == "linear" for f in status["families"])

    generated = client.post("/api/practice/generate", json={"topic": "linear equations", "difficulty": "easy", "seed": 9})
    assert generated.status_code == 200
    problem = generated.json()
    pid = problem["id"]
    assert client.get(f"/api/practice/problems/{pid}").json()["equation"] == problem["equation"]

    assert client.post(f"/api/practice/problems/{pid}/check", json={"answer": "x = 100000"}).json()["correct"] is False
    hint = client.post(f"/api/practice/problems/{pid}/hint").json()
    assert hint["hints_used"] == 1
    solution = client.post(f"/api/practice/problems/{pid}/solution").json()
    assert solution["answer"] and solution["steps"]
    assert client.post(f"/api/practice/problems/{pid}/check", json={"answer": solution["answer"]}).json()["correct"] is True

    assert client.post("/api/practice/problems/missing/check", json={"answer": "1"}).status_code == 404
    assert client.post("/api/practice/generate", json={"difficulty": "impossible"}).status_code == 422
