"""
"Learn by doing": generate word problems from course material, check the
student's answer, hand out hints and reveal a worked solution.

Pipeline for ``generate``:

1. Retrieve the most relevant course-material chunks for the topic (Chroma).
2. Ask a language model (local Qwen3-Omni or the configured OpenAI-compatible
   endpoint) for a word problem *and* the equation that models it, grounded in
   those chunks. The equation and answer are validated with the SymPy engine;
   anything the engine cannot confirm is rejected.
3. If no model is available or validation fails, fall back to a deterministic
   template generator (still topic-aware, still grounded in the retrieved
   material, always engine-verified).

Every problem carries the modelling equation so the student can compare their
own set-up with it, which is the point of the exercise.
"""

from __future__ import annotations

import logging
import random
import re
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Mapping

import sympy as sp

from config.settings import get_settings
from services import math_engine
from services.learning_style import LearningStyle
from services.common import utc_now_iso
from services.math_engine import MathParseError

logger = logging.getLogger(__name__)

DIFFICULTIES = ("easy", "medium", "hard")
NAMES = ["Maya", "Liam", "Aisha", "Noah", "Sofia", "Ethan", "Priya", "Lucas", "Zara", "Omar", "Chloe", "Ravi"]


# --------------------------------------------------------------------------- #
# Template generator
# --------------------------------------------------------------------------- #


@dataclass
class Generated:
    problem: str
    equation: str  # something math_engine.solve understands
    variable: Optional[str]
    answer: str  # the intended answer (a value or expression)
    concept: str
    hints: List[str]
    family: str
    sketch: Optional[str] = None  # what to draw on the whiteboard to see the structure


TemplateFn = Callable[[random.Random, str], Generated]


def _n(rng: random.Random, lo: int, hi: int) -> int:
    return rng.randint(lo, hi)


def _name(rng: random.Random, exclude: Optional[str] = None) -> str:
    choices = [n for n in NAMES if n != exclude]
    return rng.choice(choices)


def _hints(unknown: str, setup: str, equation: str) -> List[str]:
    return [
        f"Let {unknown}.",
        f"Set up: {setup}",
        f"The equation to solve is {equation}.",
    ]


# ---- linear ----------------------------------------------------------------


def t_membership(rng, difficulty):
    m, fee, n = _n(rng, 15, 60), _n(rng, 10, 90), _n(rng, 3, 18)
    name = _name(rng)
    total = m * n + fee
    eq = f"{m}*n + {fee} = {total}"
    return Generated(
        f"A gym charges a one-time sign-up fee of ${fee} plus ${m} per month. {name} has paid ${total} in total. "
        f"For how many months has {name} been a member?",
        eq, "n", str(n), "Two-step linear equation",
        _hints("n be the number of months", f"monthly cost × months + sign-up fee = total paid", eq), "linear",
    )


def t_shopping(rng, difficulty):
    k, pen, price = _n(rng, 2, 9), _n(rng, 2, 12), _n(rng, 3, 15)
    name = _name(rng)
    total = k * price + pen
    eq = f"{k}*x + {pen} = {total}"
    return Generated(
        f"{name} buys {k} identical notebooks and a pen that costs ${pen}. The bill comes to ${total}. "
        f"How much does one notebook cost?",
        eq, "x", str(price), "Linear equation from a shopping bill",
        _hints("x be the price of one notebook in dollars", f"{k} notebooks at x each plus the ${pen} pen equals ${total}", eq), "linear",
    )


def t_consecutive(rng, difficulty):
    first = _n(rng, 5, 60)
    s = first * 3 + 3
    eq = f"x + (x + 1) + (x + 2) = {s}"
    return Generated(
        f"The sum of three consecutive integers is {s}. What is the smallest of the three?",
        eq, "x", str(first), "Consecutive integers",
        _hints("x be the smallest integer; the others are x + 1 and x + 2", "add the three expressions and set the sum equal to the given total", eq), "linear",
    )


def t_ages(rng, difficulty):
    other_now = _n(rng, 4, 14)
    years = _n(rng, 2, 8)
    gap = other_now + years  # so that (other + gap + years) = 2*(other + years)
    a, b = _name(rng), None
    b = _name(rng, exclude=a)
    eq = f"(x + {gap}) + {years} = 2*(x + {years})"
    return Generated(
        f"{a} is {gap} years older than {b}. In {years} years, {a} will be exactly twice as old as {b}. "
        f"How old is {b} now?",
        eq, "x", str(other_now), "Age problem (linear)",
        _hints(f"x be {b}'s age now, so {a} is x + {gap}", f"in {years} years their ages are x + {years} and x + {gap} + {years}; the second is twice the first", eq), "linear",
    )


# ---- proportion / percent ----------------------------------------------------


def t_recipe(rng, difficulty):
    per = _n(rng, 1, 4)          # cups per batch
    batch = rng.choice([6, 8, 10, 12])
    mult = _n(rng, 2, 6)
    cookies = batch * mult
    cups = per * mult
    eq = f"x/{cookies} = {per}/{batch}"
    return Generated(
        f"A recipe uses {per} cup{'s' if per > 1 else ''} of flour to make {batch} cookies. "
        f"How many cups of flour are needed for {cookies} cookies?",
        eq, "x", str(cups), "Direct proportion",
        _hints("x be the cups of flour needed", "cups per cookie stays constant, so the two ratios are equal", eq), "proportion",
    )


def t_map_scale(rng, difficulty):
    cm_per = _n(rng, 1, 3)
    km_per = rng.choice([5, 10, 20, 25, 50])
    cm = cm_per * _n(rng, 2, 9)
    km = km_per * cm // cm_per
    eq = f"x/{cm} = {km_per}/{cm_per}"
    return Generated(
        f"On a map, {cm_per} cm represents {km_per} km. Two towns are {cm} cm apart on the map. "
        f"What is the real distance between them, in km?",
        eq, "x", str(km), "Scale and proportion",
        _hints("x be the real distance in km", "real distance ÷ map distance is the same for every pair of points", eq), "proportion",
    )


def t_discount(rng, difficulty):
    p = rng.choice([10, 15, 20, 25, 30, 40, 50])
    original = 20 * _n(rng, 2, 12)
    sale = original * (100 - p) // 100
    eq = f"x*(1 - {p}/100) = {sale}"
    return Generated(
        f"After a {p}% discount, a jacket costs ${sale}. What was its original price?",
        eq, "x", str(original), "Percent decrease",
        _hints("x be the original price", f"paying after a {p}% discount means paying {100 - p}% of the original price", eq), "percent",
    )


def t_simple_interest(rng, difficulty):
    principal = 100 * _n(rng, 5, 40)
    rate = rng.choice([2, 3, 4, 5, 6, 8])
    years = _n(rng, 2, 6)
    interest = principal * rate * years // 100
    name = _name(rng)
    eq = f"{principal}*(r/100)*{years} = {interest}"
    return Generated(
        f"{name} deposits ${principal} in an account paying simple interest. After {years} years the account has earned "
        f"${interest} in interest. What is the annual interest rate, in percent?",
        eq, "r", str(rate), "Simple interest",
        _hints("r be the annual rate in percent", "simple interest = principal × rate × time", eq), "percent",
    )


# ---- motion -------------------------------------------------------------------


def t_speed(rng, difficulty):
    speed = rng.choice([40, 45, 50, 60, 70, 80, 90])
    hours = _n(rng, 2, 7)
    dist = speed * hours
    eq = f"{hours}*v = {dist}"
    return Generated(
        f"A train covers {dist} km in {hours} hours at a constant speed. What is its speed in km/h?",
        eq, "v", str(speed), "Distance = speed × time",
        _hints("v be the speed in km/h", "distance equals speed multiplied by time", eq), "motion",
    )


def t_meeting(rng, difficulty):
    a, b = rng.choice([12, 15, 18, 20]), rng.choice([10, 14, 16, 22])
    hours = _n(rng, 2, 5)
    dist = (a + b) * hours
    eq = f"({a} + {b})*t = {dist}"
    return Generated(
        f"Two cyclists start {dist} km apart and ride toward each other, one at {a} km/h and the other at {b} km/h. "
        f"After how many hours do they meet?",
        eq, "t", str(hours), "Relative speed",
        _hints("t be the time in hours until they meet", "together they close the gap at the sum of their speeds", eq), "motion",
    )


# ---- geometry -----------------------------------------------------------------


def t_perimeter(rng, difficulty):
    w = _n(rng, 3, 20)
    k = _n(rng, 2, 12)
    perim = 2 * (w + (w + k))
    eq = f"2*(w + (w + {k})) = {perim}"
    return Generated(
        f"A rectangle has a perimeter of {perim} cm. Its length is {k} cm more than its width. Find the width.",
        eq, "w", str(w), "Perimeter of a rectangle",
        _hints("w be the width, so the length is w + " + str(k), "perimeter = 2 × (width + length)", eq), "geometry",
    )


def t_garden_area(rng, difficulty):
    w = _n(rng, 3, 15)
    k = _n(rng, 1, 9)
    area = w * (w + k)
    eq = f"w*(w + {k}) = {area}"
    return Generated(
        f"A rectangular garden is {k} m longer than it is wide and has an area of {area} m². What is its width?",
        eq, "w", str(w), "Quadratic from area",
        _hints(f"w be the width in metres, so the length is w + {k}", "area = width × length, which gives a quadratic", eq), "quadratic",
    )


def t_circle(rng, difficulty):
    r = _n(rng, 2, 12)
    eq = f"pi*r^2 = {r * r}*pi"
    return Generated(
        f"A circular pond has an area of {r * r}π m². What is its radius?",
        eq, "r", str(r), "Area of a circle",
        _hints("r be the radius", "area of a circle is πr²", eq), "geometry",
    )


# ---- quadratic / systems -----------------------------------------------------


def t_projectile(rng, difficulty):
    t1, t2 = _n(rng, 2, 6), _n(rng, 1, 3)  # roots t1 and -t2
    v, h0 = 5 * (t1 - t2), 5 * t1 * t2
    eq = f"-5*t^2 + {v}*t + {h0} = 0"
    return Generated(
        f"A ball is thrown from a ledge. Its height in metres after t seconds is h(t) = -5t² + {v}t + {h0}. "
        f"After how many seconds does it hit the ground?",
        eq, "t", str(t1), "Quadratic equation (projectile)",
        _hints("t be the time in seconds when the height is zero", "hitting the ground means h(t) = 0; factor or use the quadratic formula and keep the positive root", eq), "quadratic",
    )


def t_tickets(rng, difficulty):
    adult, child = rng.choice([8, 10, 12, 15]), rng.choice([4, 5, 6])
    adults, children = _n(rng, 10, 60), _n(rng, 10, 60)
    total_n, total_money = adults + children, adult * adults + child * children
    eq = f"{adult}*x + {child}*({total_n} - x) = {total_money}"
    return Generated(
        f"Adult tickets cost ${adult} and child tickets cost ${child}. A show sold {total_n} tickets for a total of "
        f"${total_money}. How many adult tickets were sold?",
        eq, "x", str(adults), "Two quantities, one equation",
        _hints(f"x be the number of adult tickets, so {total_n} - x are child tickets", "adult revenue + child revenue = total revenue", eq), "systems",
    )


# ---- exponential ----------------------------------------------------------------


def t_doubling(rng, difficulty):
    n0 = rng.choice([50, 100, 200, 250, 500])
    hours = _n(rng, 2, 6)
    n = n0 * 2 ** hours
    eq = f"{n0}*2^t = {n}"
    return Generated(
        f"A bacteria culture starts with {n0} cells and doubles every hour. After how many hours will there be {n} cells?",
        eq, "t", str(hours), "Exponential growth",
        _hints("t be the number of hours", f"after t doublings there are {n0}·2^t cells", eq), "exponential",
    )


# ---- calculus ---------------------------------------------------------------------


def t_velocity(rng, difficulty):
    a, b, c = _n(rng, 1, 5), _n(rng, 1, 9), _n(rng, 0, 20)
    expr = f"{a}*t^3 - {b}*t^2 + {c}"
    eq = f"derivative of {expr}"
    answer = str(sp.diff(sp.sympify(expr.replace("^", "**")), sp.Symbol("t")))
    return Generated(
        f"A particle moves along a line so that its position at time t seconds is s(t) = {a}t³ − {b}t² + {c} metres. "
        f"Find an expression for its velocity v(t).",
        eq, "t", answer, "Derivative as rate of change",
        _hints("v(t) be the derivative of the position function", "differentiate term by term using the power rule", eq), "calculus",
    )


def t_distance(rng, difficulty):
    a, b = _n(rng, 1, 4), _n(rng, 1, 6)
    upper = _n(rng, 2, 5)
    expr = f"{a}*t^2 + {b}"
    eq = f"integrate {expr} from 0 to {upper}"
    answer = str(sp.integrate(sp.sympify(expr.replace("^", "**")), (sp.Symbol("t"), 0, upper)))
    return Generated(
        f"A car's velocity is v(t) = {a}t² + {b} metres per second. How far does it travel between t = 0 and t = {upper} seconds?",
        eq, None, answer, "Definite integral as accumulated change",
        _hints("distance be the area under the velocity curve", f"integrate v(t) from 0 to {upper}", eq), "calculus",
    )


FAMILIES: Dict[str, Dict[str, Any]] = OrderedDict(
    [
        ("linear", {"label": "Linear equations", "keywords": ["linear", "one-step", "two-step", "solve for", "equation", "algebra", "unknown", "variable", "age"],
                    "templates": [t_membership, t_shopping, t_consecutive, t_ages], "difficulty": {"easy": [t_shopping, t_consecutive], "medium": [t_membership, t_shopping], "hard": [t_ages, t_membership]}}),
        ("proportion", {"label": "Ratios and proportion", "keywords": ["ratio", "proportion", "rate", "scale", "unit rate", "recipe", "per"],
                        "templates": [t_recipe, t_map_scale], "difficulty": {"easy": [t_recipe], "medium": [t_map_scale, t_recipe], "hard": [t_map_scale]}}),
        ("percent", {"label": "Percentages and interest", "keywords": ["percent", "%", "discount", "sale", "interest", "tax", "markup", "increase", "decrease"],
                     "templates": [t_discount, t_simple_interest], "difficulty": {"easy": [t_discount], "medium": [t_discount, t_simple_interest], "hard": [t_simple_interest]}}),
        ("motion", {"label": "Speed, distance and time", "keywords": ["speed", "distance", "time", "velocity", "km/h", "travel", "train", "car", "motion"],
                    "templates": [t_speed, t_meeting], "difficulty": {"easy": [t_speed], "medium": [t_meeting, t_speed], "hard": [t_meeting]}}),
        ("geometry", {"label": "Perimeter and area", "keywords": ["perimeter", "area", "rectangle", "circle", "radius", "geometry", "triangle", "width", "length"],
                      "templates": [t_perimeter, t_circle], "difficulty": {"easy": [t_perimeter], "medium": [t_perimeter, t_circle], "hard": [t_circle]}}),
        ("quadratic", {"label": "Quadratic equations", "keywords": ["quadratic", "square", "roots", "factor", "parabola", "projectile", "x^2", "x²"],
                       "templates": [t_garden_area, t_projectile], "difficulty": {"easy": [t_garden_area], "medium": [t_garden_area, t_projectile], "hard": [t_projectile]}}),
        ("systems", {"label": "Mixtures and tickets", "keywords": ["system", "two variables", "tickets", "coins", "mixture", "simultaneous"],
                     "templates": [t_tickets], "difficulty": {"easy": [t_tickets], "medium": [t_tickets], "hard": [t_tickets]}}),
        ("exponential", {"label": "Exponential growth", "keywords": ["exponential", "growth", "decay", "double", "doubling", "half-life", "bacteria", "compound"],
                         "templates": [t_doubling], "difficulty": {"easy": [t_doubling], "medium": [t_doubling], "hard": [t_doubling]}}),
        ("calculus", {"label": "Derivatives and integrals", "keywords": ["derivative", "differentiate", "integral", "integrate", "calculus", "rate of change", "velocity", "acceleration", "area under"],
                      "templates": [t_velocity, t_distance], "difficulty": {"easy": [t_velocity], "medium": [t_velocity, t_distance], "hard": [t_distance]}}),
    ]
)

_DEFAULT_BY_DIFFICULTY = {
    "easy": ["linear", "proportion", "percent", "motion"],
    "medium": ["linear", "geometry", "percent", "motion", "systems"],
    "hard": ["quadratic", "systems", "exponential", "calculus", "linear"],
}


def _keyword_pattern(keyword: str) -> "re.Pattern[str]":
    if re.fullmatch(r"[\w\s/-]+", keyword):
        return re.compile(rf"\b{re.escape(keyword)}\b", re.IGNORECASE)
    return re.compile(re.escape(keyword), re.IGNORECASE)


_KEYWORD_PATTERNS: Dict[str, List["re.Pattern[str]"]] = {
    family: [_keyword_pattern(kw) for kw in spec["keywords"]] + [_keyword_pattern(family)] for family, spec in FAMILIES.items()
}


def pick_family(topic: str, context_text: str, difficulty: str, rng: random.Random) -> str:
    """
    Choose a problem family. The student's explicit topic dominates; retrieved
    course material only breaks ties / fills in when the topic is vague.
    """
    topic_scores: Dict[str, float] = {}
    context_scores: Dict[str, float] = {}
    for family, patterns in _KEYWORD_PATTERNS.items():
        topic_hits = sum(1 for p in patterns if p.search(topic))
        context_hits = sum(min(len(p.findall(context_text)), 4) for p in patterns)
        if topic_hits:
            topic_scores[family] = topic_hits * 5.0
        if context_hits:
            context_scores[family] = context_hits * 0.3
    if topic_scores:
        best = max(topic_scores.values())
        candidates = [f for f, s in topic_scores.items() if s >= best]
        if len(candidates) > 1:  # tie on topic words: let the material decide
            candidates.sort(key=lambda f: context_scores.get(f, 0.0), reverse=True)
            top = context_scores.get(candidates[0], 0.0)
            candidates = [f for f in candidates if context_scores.get(f, 0.0) >= top]
        return rng.choice(candidates)
    if context_scores:
        best = max(context_scores.values())
        return rng.choice([f for f, s in context_scores.items() if s >= best * 0.75])
    return rng.choice(_DEFAULT_BY_DIFFICULTY[difficulty])


def generate_from_templates(topic: str, difficulty: str, context_text: str, rng: random.Random, family: Optional[str] = None) -> Generated:
    family = family if family in FAMILIES else pick_family(topic, context_text, difficulty, rng)
    spec = FAMILIES[family]
    templates: Sequence[TemplateFn] = spec["difficulty"].get(difficulty) or spec["templates"]
    return rng.choice(list(templates))(rng, difficulty)


# --------------------------------------------------------------------------- #
# Engine validation helpers
# --------------------------------------------------------------------------- #


def _engine_check(equation: str, answer: str) -> Tuple[bool, Optional[math_engine.MathResult], str]:
    """Confirm the engine can solve ``equation`` and that ``answer`` is one of its solutions."""
    try:
        result = math_engine.solve(equation)
    except MathParseError as exc:
        return False, None, f"engine cannot parse equation: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, None, f"engine failed: {exc}"
    ok, _ = _answer_matches(result, answer)
    return ok, result, "" if ok else f"answer {answer!r} does not match engine solution {result.solution!r}"


def _answer_matches(result: math_engine.MathResult, answer: str) -> Tuple[bool, bool]:
    """Return (matches_intended_solution_set, matched_any_root)."""
    try:
        proposed = math_engine._parse_proposed_values(answer)  # noqa: SLF001
    except MathParseError:
        return False, False
    if not proposed:
        return False, False
    if result.problem_type in ("equation",):
        roots = list(result.result) if isinstance(result.result, (list, tuple, set)) else [result.result]
        for p in proposed:
            if any(_equal(p, r) for r in roots):
                return True, True
        return False, False
    if result.problem_type in ("inequality", "system"):
        return math_engine.normalize_text(answer).replace(" ", "") == result.solution.replace(" ", ""), False
    expected = result.result
    for p in proposed:
        diff = sp.simplify(p - expected)
        if result.problem_type == "integral" and getattr(diff, "is_constant", lambda: False)():
            return True, True
        if diff == 0 or (not diff.free_symbols and abs(complex(sp.N(diff))) < 1e-9):
            return True, True
    return False, False


def _equal(a: sp.Basic, b: sp.Basic) -> bool:
    try:
        diff = sp.simplify(a - b)
        if diff == 0:
            return True
        if not diff.free_symbols:
            return abs(complex(sp.N(diff))) < 1e-9
    except Exception:  # noqa: BLE001
        pass
    return False


# --------------------------------------------------------------------------- #
# Service
# --------------------------------------------------------------------------- #


@dataclass
class PracticeProblem:
    id: str
    topic: str
    difficulty: str
    family: str
    concept: str
    problem: str
    equation: str
    equation_latex: str
    variable: Optional[str]
    answer: str
    answer_display: str
    hints: List[str]
    sources: List[Dict[str, Any]]
    generator: str
    sketch: Optional[str] = None
    learning_style: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=utc_now_iso)
    attempts: int = 0
    hints_used: int = 0
    solved: bool = False
    revealed: bool = False
    note: Optional[str] = None

    def public(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "topic": self.topic,
            "difficulty": self.difficulty,
            "family": self.family,
            "family_label": FAMILIES.get(self.family, {}).get("label", self.family),
            "concept": self.concept,
            "problem": self.problem,
            "equation": self.equation,
            "equation_latex": self.equation_latex,
            "variable": self.variable,
            "hints_available": len(self.hints),
            "hints_used": self.hints_used,
            "hints": self.hints[: self.hints_used],
            "sources": self.sources,
            "generator": self.generator,
            "sketch": self.sketch,
            "learning_style": self.learning_style,
            "note": self.note,
            "attempts": self.attempts,
            "solved": self.solved,
            "revealed": self.revealed,
            "created_at": self.created_at,
        }


# What to draw for each family when the template generator is used. Written
# generically so they hold for every template in the family.
FAMILY_SKETCHES: Dict[str, str] = {
    "linear": "Draw a bar model: one bar for the total, split into the fixed part and equal-sized repeated parts; label each piece.",
    "proportion": "Draw a double number line or a 2x2 ratio table with the known pair on one row and the unknown pair on the other.",
    "percent": "Draw a 100% bar, shade the percentage involved, and write the money amounts under the whole bar and the shaded part.",
    "motion": "Sketch a distance-time graph: a straight line for each mover, the slope is the speed; mark where lines meet or reach the target distance.",
    "geometry": "Draw the shape roughly to scale and label every side or radius with its number or expression.",
    "quadratic": "Sketch the rectangle (label w and the longer side) or the parabola with its start height and the level you are solving for.",
    "systems": "Draw a two-column table: one row per kind of item, columns for how many and how much money; the totals row gives the equation.",
    "exponential": "Draw a table doubling step by step, then plot the points to see the curve bend upwards.",
    "calculus": "Sketch the graph of the given function; the derivative is its slope, the definite integral is the shaded area between the limits.",
}


_LLM_SYSTEM = (
    "You write short, realistic word problems for a math student, grounded in the course material provided. "
    "Reply with ONLY a JSON object with keys: "
    "\"problem\" (the word problem, 1-3 sentences, concrete numbers, one unknown), "
    "\"equation\" (ONE equation or command a computer-algebra system can solve, using ^ for powers, * for "
    "multiplication, e.g. '12*x + 30 = 150', 'w*(w + 3) = 40', 'derivative of 3*t^2 + 2*t', "
    "'integrate 2*t from 0 to 4'), "
    "\"variable\" (the unknown's letter, or null), "
    "\"answer\" (the intended final answer as a number or expression, e.g. '10' or '6*t + 2'), "
    "\"concept\" (2-6 words naming the skill), "
    "\"hints\" (array of exactly 3 progressively more specific hints; the last one may state the equation), "
    "and optionally \"sketch\" (one sentence: what to draw to see the structure of the problem). "
    "Rules for \"equation\": only digits, operators, parentheses, known functions (sqrt, sin, ...) and ONE unknown "
    "written as a single lowercase letter other than e (prefer x, n, t, m, p, r, w); never use words, units, currency "
    "symbols or percent signs (write 25% as 0.25 or 25/100). Rules for \"answer\": it must be exactly what solving "
    "your equation yields - a number for an equation, the resulting expression for 'derivative of' / 'integrate' / "
    "'simplify' commands (not a value at some point). "
    "The problem must be solvable exactly with the equation you give. No prose outside the JSON."
)


class PracticeService:
    def __init__(self, settings=None, knowledge=None, ai=None):
        self.settings = settings or get_settings()
        self.knowledge = knowledge
        self.ai = ai
        self._problems: "OrderedDict[str, PracticeProblem]" = OrderedDict()
        self._max_problems = 500
        self._stats = {"generated": 0, "solved": 0, "first_try": 0, "attempts": 0, "revealed": 0, "streak": 0, "best_streak": 0, "by_family": {}}
        self.is_initialized = False

    async def initialize(self) -> None:
        self.is_initialized = True

    async def cleanup(self) -> None:
        self.is_initialized = False

    def is_healthy(self) -> bool:
        return self.is_initialized

    # ---- metadata ------------------------------------------------------ #

    def families(self) -> List[Dict[str, Any]]:
        return [{"id": fid, "label": spec["label"], "keywords": spec["keywords"][:4]} for fid, spec in FAMILIES.items()]

    def status(self) -> Dict[str, Any]:
        return {
            "llm_available": bool(self.ai and self.ai.any_llm_available),
            "llm": self.ai.llm_name if self.ai else None,
            "knowledge_available": bool(self.knowledge and self.knowledge.is_initialized),
            "documents": len(self.knowledge.list_documents()) if self.knowledge and self.knowledge.is_initialized else 0,
            "families": self.families(),
            "difficulties": list(DIFFICULTIES),
            "stats": self.stats(),
        }

    def stats(self) -> Dict[str, Any]:
        return {**self._stats, "by_family": dict(self._stats["by_family"])}

    # ---- generation ----------------------------------------------------- #

    async def generate(
        self,
        topic: str,
        difficulty: str = "medium",
        *,
        doc_ids: Optional[List[str]] = None,
        family: Optional[str] = None,
        mode: str = "auto",
        seed: Optional[int] = None,
        learning_style: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:
        topic = (topic or "").strip() or "general practice"
        style = LearningStyle.from_mapping(learning_style)
        difficulty = difficulty if difficulty in DIFFICULTIES else "medium"
        rng = random.Random(seed)
        started = time.perf_counter()

        sources = self._retrieve(topic, doc_ids)
        context_text = "\n\n".join(s["text"] for s in sources)

        generated: Optional[Generated] = None
        engine_result: Optional[math_engine.MathResult] = None
        generator = "templates"
        note: Optional[str] = None

        want_llm = mode in ("auto", "llm") and self.ai is not None and self.ai.any_llm_available
        if want_llm:
            generated, engine_result, failure = await self._generate_with_llm(topic, difficulty, sources, family, style)
            if generated is not None:
                generator = self.ai.llm_name or "llm"
            else:
                logger.info("LLM practice generation rejected (%s); using templates", failure)
                note = f"The language model's problem could not be verified ({failure}); showing a template problem instead."
        elif mode == "llm":
            note = "No language model is available; showing a template problem instead."

        if generated is None:
            generated = generate_from_templates(topic, difficulty, context_text, rng, family)
            ok, engine_result, failure = _engine_check(generated.equation, generated.answer)
            if not ok:  # should never happen; templates are engine-verified by construction
                logger.error("Template %s failed engine check: %s", generated.family, failure)
                generated = t_shopping(rng, difficulty)
                _, engine_result, _ = _engine_check(generated.equation, generated.answer)
            if sources:
                note = note or f"Grounded in your course material: {', '.join(sorted({s['title'] for s in sources}))}."

        assert engine_result is not None
        problem = PracticeProblem(
            id=uuid.uuid4().hex[:10],
            topic=topic,
            difficulty=difficulty,
            family=generated.family,
            concept=generated.concept,
            problem=generated.problem,
            equation=generated.equation,
            equation_latex=self._equation_latex(generated.equation),
            variable=generated.variable,
            answer=generated.answer,
            answer_display=self._display_answer(generated, engine_result),
            hints=generated.hints[:3],
            sources=sources,
            generator=generator,
            sketch=generated.sketch or FAMILY_SKETCHES.get(generated.family),
            learning_style=style.to_dict() if style else None,
            note=note,
        )
        self._remember(problem)
        self._stats["generated"] += 1
        fam = self._stats["by_family"]
        fam[problem.family] = fam.get(problem.family, 0) + 1
        payload = problem.public()
        payload["processing_time"] = round(time.perf_counter() - started, 3)
        return payload

    def _retrieve(self, topic: str, doc_ids: Optional[List[str]]) -> List[Dict[str, Any]]:
        if not (self.knowledge and self.knowledge.is_initialized and self.knowledge.has_documents()):
            return []
        try:
            # No similarity threshold: when the student asks for practice, the most
            # relevant material they uploaded is always the right grounding.
            hits = self.knowledge.search(topic, k=4, doc_ids=doc_ids)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Knowledge retrieval failed: %s", exc)
            return []
        return [
            {
                "doc_id": h["doc_id"],
                "title": h["title"],
                "page": h["page"],
                "score": h["score"],
                "text": h["text"],
                "snippet": (h["text"][:280] + "…") if len(h["text"]) > 280 else h["text"],
            }
            for h in hits
        ]

    async def _generate_with_llm(self, topic, difficulty, sources, family, style: Optional[LearningStyle] = None) -> Tuple[Optional[Generated], Optional[math_engine.MathResult], str]:
        from services.ai_service import NoLanguageModelError

        excerpts = "\n\n".join(f"[{s['title']}{f', p.{s['page']}' if s['page'] else ''}]\n{s['text'][:1200]}" for s in sources) or "(no course material uploaded; use general knowledge)"
        family_hint = f" The problem should exercise: {FAMILIES[family]['label']}." if family in FAMILIES else ""
        style_hint = f"\n\n{style.prompt_hint()}" if style and style.prompt_hint() else ""
        user = (
            f"Topic: {topic}\nDifficulty: {difficulty}.{family_hint}\n\nCourse material excerpts:\n{excerpts}{style_hint}\n\n"
            "Write one word problem that practises exactly this material."
        )
        failure = ""
        for attempt in range(3):
            prompt = user
            if failure:
                prompt = (
                    f"{user}\n\nYour previous attempt was rejected by the computer-algebra checker: {failure}. "
                    "Fix it: use a single-letter unknown, no words or units inside the equation, and make sure the "
                    "answer is exactly what the equation yields. Return the corrected JSON."
                )
            try:
                data = await self.ai.complete_json(_LLM_SYSTEM, prompt)
            except NoLanguageModelError as exc:
                return None, None, str(exc)
            problem = str(data.get("problem", "")).strip()
            equation = str(data.get("equation", "")).strip()
            answer = str(data.get("answer", "")).strip()
            hints = [str(h).strip() for h in data.get("hints", []) if str(h).strip()][:3]
            if not problem or not equation or not answer:
                failure = "missing problem, equation or answer"
                continue
            ok, result, failure = _engine_check(equation, answer)
            if not ok:
                continue
            while len(hints) < 3:
                hints.append(f"The equation to solve is {equation}.")
            fam = family if family in FAMILIES else pick_family(f"{topic} {data.get('concept', '')}", problem, difficulty, random.Random(0))
            sketch = str(data.get("sketch") or "").strip() or None
            return (
                Generated(problem, equation, data.get("variable") or result.variable, answer, str(data.get("concept") or FAMILIES[fam]["label"]), hints, fam, sketch),
                result,
                "",
            )
        return None, None, failure or "unknown"

    @staticmethod
    def _equation_latex(equation: str) -> str:
        """LaTeX for the equation *as written* (unevaluated), so the set-up stays visible."""
        try:
            if "=" in equation and not re.match(r"^\s*(derivative|d/d|integrate|limit|simplify|factor|expand)", equation, re.I):
                parts = math_engine._split_equation(math_engine.normalize_text(equation))  # noqa: SLF001
                if parts:
                    lhs, rhs = parts
                    local = {"pi": sp.pi, "e": sp.E, "E": sp.E}
                    to_tex = lambda s: sp.latex(sp.sympify(s.replace("^", "**"), locals=local, evaluate=False))  # noqa: E731
                    return f"{to_tex(lhs)} = {to_tex(rhs)}"
        except Exception:  # noqa: BLE001
            pass
        return ""

    @staticmethod
    def _display_answer(generated: Generated, result: math_engine.MathResult) -> str:
        if generated.variable and result.problem_type == "equation":
            return f"{generated.variable} = {generated.answer}"
        return generated.answer

    def _remember(self, problem: PracticeProblem) -> None:
        self._problems[problem.id] = problem
        while len(self._problems) > self._max_problems:
            self._problems.popitem(last=False)

    # ---- interaction ----------------------------------------------------- #

    def get(self, problem_id: str) -> Optional[PracticeProblem]:
        return self._problems.get(problem_id)

    def check(self, problem_id: str, answer: str) -> Dict[str, Any]:
        problem = self._problems.get(problem_id)
        if problem is None:
            raise KeyError(problem_id)
        answer = (answer or "").strip()
        if not answer:
            raise ValueError("Enter an answer first.")

        try:
            proposed = math_engine._parse_proposed_values(answer)  # noqa: SLF001
        except MathParseError:
            proposed = []
        if not proposed:
            # Typos should not burn an attempt or trigger hints.
            return {
                "problem_id": problem.id,
                "correct": False,
                "unreadable": True,
                "feedback": "I couldn't read that as a number or expression. Try something like 12, 3/4 or x = 12.",
                "attempts": problem.attempts,
                "solved": problem.solved,
                "hint": None,
                "hints_used": problem.hints_used,
                "hints_available": len(problem.hints),
                "answer": None,
                "stats": self.stats(),
                "timestamp": utc_now_iso(),
            }

        problem.attempts += 1
        self._stats["attempts"] += 1
        try:
            result = math_engine.solve(problem.equation)
        except MathParseError as exc:  # cannot happen for stored problems, but stay safe
            raise ValueError(f"Stored equation is invalid: {exc}") from exc

        try:
            intended = math_engine.parse_expression(problem.answer)
            intended_ok = any(_equal(p, intended) for p in proposed)
        except MathParseError:
            intended_ok = False
        matches_set, matched_root = (intended_ok, intended_ok) if intended_ok else _answer_matches(result, answer)

        if intended_ok or (matches_set and result.problem_type != "equation"):
            correct = True
            feedback = "Correct! Your answer matches the model." if problem.attempts == 1 else f"Correct on attempt {problem.attempts}."
        elif matched_root:
            correct = False
            feedback = (
                f"{answer} does solve the equation, but it isn't a valid answer in this situation "
                "(think about which values make sense for the quantity you defined)."
            )
        else:
            correct = False
            feedback = "Not quite. Check your set-up and try again." if problem.attempts < 2 else "Still not right. Use a hint or reveal the equation."

        next_hint: Optional[str] = None
        if correct:
            if not problem.solved:
                problem.solved = True
                self._stats["solved"] += 1
                if problem.attempts == 1 and problem.hints_used == 0 and not problem.revealed:
                    self._stats["first_try"] += 1
                self._stats["streak"] += 1
                self._stats["best_streak"] = max(self._stats["best_streak"], self._stats["streak"])
        else:
            if problem.attempts == 1:
                self._stats["streak"] = 0
            if problem.attempts >= 2 and problem.hints_used < len(problem.hints):
                next_hint = problem.hints[problem.hints_used]
                problem.hints_used += 1

        return {
            "problem_id": problem.id,
            "correct": correct,
            "unreadable": False,
            "feedback": feedback,
            "attempts": problem.attempts,
            "solved": problem.solved,
            "hint": next_hint,
            "hints_used": problem.hints_used,
            "hints_available": len(problem.hints),
            "answer": problem.answer_display if correct else None,
            "stats": self.stats(),
            "timestamp": utc_now_iso(),
        }

    def hint(self, problem_id: str) -> Dict[str, Any]:
        problem = self._problems.get(problem_id)
        if problem is None:
            raise KeyError(problem_id)
        if problem.hints_used < len(problem.hints):
            problem.hints_used += 1
        return {
            "problem_id": problem.id,
            "hints": problem.hints[: problem.hints_used],
            "hints_used": problem.hints_used,
            "hints_available": len(problem.hints),
            "exhausted": problem.hints_used >= len(problem.hints),
        }

    def solution(self, problem_id: str) -> Dict[str, Any]:
        problem = self._problems.get(problem_id)
        if problem is None:
            raise KeyError(problem_id)
        result = math_engine.solve(problem.equation)
        if not problem.revealed:
            problem.revealed = True
            self._stats["revealed"] += 1
            if not problem.solved:
                self._stats["streak"] = 0
        extra: List[str] = []
        if result.problem_type == "equation" and isinstance(result.result, (list, tuple, set)) and len(result.result) > 1:
            extra.append(
                f"The equation has {len(result.result)} solutions ({result.solution}); only {problem.answer_display} makes sense for this situation."
            )
        return {
            "problem_id": problem.id,
            "equation": problem.equation,
            "equation_latex": problem.equation_latex,
            "answer": problem.answer_display,
            "engine_solution": result.solution,
            "solution_latex": result.solution_latex,
            "steps": [f"Model the situation: {problem.equation}"] + list(result.steps) + extra,
            "sketch": problem.sketch,
            "hints": problem.hints,
            "stats": self.stats(),
            "timestamp": utc_now_iso(),
        }
