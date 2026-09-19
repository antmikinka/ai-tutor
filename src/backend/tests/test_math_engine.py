import pytest
import sympy as sp

from services import math_engine
from services.math_engine import MathParseError, solve, verify


@pytest.mark.parametrize(
    "problem,expected_type,expected_solution",
    [
        ("solve x^2 + 2x + 1 = 0", "equation", "x = -1"),
        ("x^2 - 5x + 6 = 0", "equation", "x = 2 or x = 3"),
        ("solve for y: 2y - 4 = 10", "equation", "y = 7"),
        ("x squared minus 4 equals 0", "equation", "x = -2 or x = 2"),
        ("2x + 3 = 7 and x - y = 1", "system", "x = 2, y = 1"),
        ("derivative of x^3 + sin(x)", "derivative", "f'(x) = 3*x**2 + cos(x)"),
        ("d/dx x^3", "derivative", "f'(x) = 3*x**2"),
        ("integrate x^2 from 0 to 3", "definite_integral", "9"),
        ("integrate sin(x) dx", "integral", "-cos(x) + C"),
        ("limit of sin(x)/x as x->0", "limit", "1"),
        ("limit of (1+1/n)^n as n -> oo", "limit", "E"),
        ("simplify (x^2-1)/(x-1)", "simplify", "x + 1"),
        ("factor x^2 - 5x + 6", "factor", "(x - 3)*(x - 2)"),
        ("expand (x+1)^3", "expand", "x**3 + 3*x**2 + 3*x + 1"),
        ("3*4+2", "evaluate", "14"),
        ("sqrt(16) + 2^3", "evaluate", "12"),
        ("2 + 2", "evaluate", "4"),
    ],
)
def test_solve_deterministic(problem, expected_type, expected_solution):
    result = solve(problem)
    assert result.problem_type == expected_type
    assert result.solution == expected_solution
    assert result.steps, "every solution must come with steps"
    assert 0 < result.confidence <= 1


def test_solve_is_repeatable():
    a = solve("solve x^2 - 2 = 0")
    b = solve("solve x^2 - 2 = 0")
    assert a.to_dict() == b.to_dict()


def test_inequality():
    result = solve("x^2 > 4")
    assert result.problem_type == "inequality"
    assert "-2" in result.solution and "2 < x" in result.solution


def test_approximation_only_when_useful():
    assert solve("integrate x^2 from 0 to 3").approximation is None
    assert solve("solve x^2 = 2").approximation.startswith("x ≈ -1.41421")
    assert solve("1/3 + 1/6").approximation is None


def test_latex_output():
    result = solve("derivative of x^2")
    assert result.solution_latex == "2 x"


@pytest.mark.parametrize(
    "malicious",
    [
        '__import__("os").system("ls")',
        "x.__class__.__mro__",
        'open("/etc/passwd")',
        "lambda: 1",
        "exec('1')",
        "import os",
    ],
)
def test_parser_rejects_code(malicious):
    with pytest.raises(MathParseError):
        solve(malicious)


def test_empty_and_nonsense():
    with pytest.raises(MathParseError):
        solve("   ")
    with pytest.raises(MathParseError):
        solve("what is the meaning of life")


def test_verify_equation_correct_and_partial():
    assert verify("solve x^2 - 4 = 0", "x = 2, x = -2")["is_correct"] is True
    partial = verify("solve x^2 - 4 = 0", "x = 2")
    assert partial["is_correct"] is False
    assert partial["feedback"].startswith("Partially correct")


def test_verify_derivative_and_integral():
    assert verify("derivative of x^2", "2x")["is_correct"] is True
    assert verify("derivative of x^2", "x")["is_correct"] is False
    # antiderivatives differ by a constant
    assert verify("integrate x^2", "x^3/3 + 5")["is_correct"] is True


def test_verify_handles_unparseable_solution():
    verdict = verify("solve x + 1 = 2", "banana!!")
    assert verdict["is_correct"] is False
    assert "Expected" in verdict["feedback"]


def test_normalize_text_unicode():
    assert math_engine.normalize_text("x² ÷ 2 × 3") == "x^2 / 2 * 3"


def test_detect_problem_type():
    assert math_engine.detect_problem_type("What is the derivative of x^2?") == "derivative"
    assert math_engine.detect_problem_type("2x = 4") == "solve"
    assert math_engine.detect_problem_type("x < 3") == "inequality"
    assert math_engine.detect_problem_type("2 + 2") == "evaluate"


def test_result_raw_object_is_sympy():
    assert isinstance(solve("derivative of x^2").result, sp.Basic)


def test_interest_and_energy_letters_are_variables_when_needed():
    # "I" is SymPy's imaginary unit, but here it clearly means interest.
    result = solve("1200*0.05*3 = I")
    assert result.problem_type == "equation" and result.variable == "I"
    assert result.solution.replace(" ", "") in {"I=180", "I=180.0", "I=180.000000000000"}
    energy = solve("E = 2*9.8*5")
    assert energy.variable == "E" and "98" in energy.solution
    # The imaginary unit still works where it is genuinely meant.
    assert verify("x^2 = -1", "x = I, x = -I")["is_correct"] is True


def test_constant_equation_is_a_parse_error():
    with pytest.raises(MathParseError, match="constants"):
        solve("2 + 2 = 4")
    with pytest.raises(MathParseError, match="constants"):
        solve("3*4 = 11")


def test_decimal_inputs_print_like_a_person_writes_them():
    r = solve("1200*0.05*3 = i")
    assert r.solution == "i = 180" and r.solution_latex == "i = 180" and r.approximation is None
    assert all("180.000" not in step for step in r.steps)
    assert solve("437.50 = 2500 * 0.035 * t").solution == "t = 5"
    assert solve("derivative of 0.5*t^2").solution == "f'(t) = t"
    assert solve("x^2 = 2.5").solution == "x = -1.58113883 or x = 1.58113883"
