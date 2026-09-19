"""
Deterministic symbolic math engine built on SymPy.

This is the always-available solver used by the AI service when no large
language model is loaded (and as the verification oracle when one is). It
turns natural-language-ish requests such as

    "solve x^2 + 2x + 1 = 0"
    "derivative of sin(x) * x^2"
    "integrate 2x + 3 from 0 to 2"
    "limit of sin(x)/x as x -> 0"
    "simplify (x^2 - 1)/(x - 1)"
    "what is 3 * (4 + 5)?"

into structured, step-by-step solutions. Everything is computed; nothing is
guessed or randomised.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import sympy as sp
from sympy.printing.latex import LatexPrinter
from sympy.printing.str import StrPrinter
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #

_TRANSFORMATIONS = standard_transformations + (
    implicit_multiplication_application,
    convert_xor,
)

# Names the parser is allowed to resolve. Anything else becomes a Symbol.
_ALLOWED_FUNCTIONS: Dict[str, Any] = {
    "sin": sp.sin, "cos": sp.cos, "tan": sp.tan,
    "cot": sp.cot, "sec": sp.sec, "csc": sp.csc,
    "asin": sp.asin, "acos": sp.acos, "atan": sp.atan,
    "arcsin": sp.asin, "arccos": sp.acos, "arctan": sp.atan,
    "sinh": sp.sinh, "cosh": sp.cosh, "tanh": sp.tanh,
    "exp": sp.exp, "log": sp.log, "ln": sp.log,
    "sqrt": sp.sqrt, "cbrt": sp.cbrt, "root": sp.root,
    "abs": sp.Abs, "Abs": sp.Abs,
    "factorial": sp.factorial, "gamma": sp.gamma,
    "floor": sp.floor, "ceiling": sp.ceiling, "ceil": sp.ceiling,
    "gcd": sp.gcd, "lcm": sp.lcm,
    "pi": sp.pi, "e": sp.E, "E": sp.E, "I": sp.I, "oo": sp.oo, "inf": sp.oo, "infinity": sp.oo,
}

# The names emitted by SymPy's tokenizer transformations must be resolvable
# during evaluation. Builtins are deliberately emptied so parsed text can never
# reach the Python runtime.
_GLOBAL_DICT: Dict[str, Any] = {
    "__builtins__": {},
    "Symbol": sp.Symbol,
    "Integer": sp.Integer,
    "Float": sp.Float,
    "Rational": sp.Rational,
    "Number": sp.Number,
    "Function": sp.Function,
    "factorial": sp.factorial,
    **_ALLOWED_FUNCTIONS,
}

_FORBIDDEN_TOKENS = re.compile(
    r"(__|\bimport\b|\bexec\b|\beval\b|\bopen\b|\blambda\b|\bglobals\b|\blocals\b|\bgetattr\b)",
    re.IGNORECASE,
)
_ALLOWED_CHARS = re.compile(r"^[0-9A-Za-z_+\-*/^().,=<>!\s]*$")
_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z_0-9]*")
# Multi-letter identifiers that are legitimate symbols rather than functions.
_ALLOWED_SYMBOL_NAMES = {
    "theta", "alpha", "beta", "gamma_", "delta", "Delta", "phi", "omega", "lambda_", "mu", "sigma",
    "dx", "dy", "dt",
}

_UNICODE_REPLACEMENTS = {
    "²": "^2", "³": "^3", "⁴": "^4",
    "×": "*", "·": "*", "÷": "/", "−": "-", "–": "-",
    "π": "pi", "θ": "theta", "α": "alpha", "β": "beta", "γ": "gamma_", "Δ": "Delta",
    "∞": "oo", "√": "sqrt", "≤": "<=", "≥": ">=", "≠": "!=",
    "→": "->", "⁻": "-", "½": "(1/2)", "¼": "(1/4)", "¾": "(3/4)",
}

# Spoken-form arithmetic frequently arrives from speech-to-text.
_WORD_OPERATORS: Sequence[Tuple[str, str]] = (
    (r"\bdivided by\b", "/"),
    (r"\bmultiplied by\b", "*"),
    (r"\btimes\b", "*"),
    (r"\bplus\b", "+"),
    (r"\bminus\b", "-"),
    (r"\bto the power of\b", "^"),
    (r"\bsquared\b", "^2"),
    (r"\bcubed\b", "^3"),
    (r"\bequals\b", "="),
    (r"\bis equal to\b", "="),
    (r"\bover\b", "/"),
)

# Leading/trailing filler that should be stripped before parsing an expression.
_COMMAND_PREFIXES = re.compile(
    r"^(?:please\s+)?(?:can you\s+|could you\s+)?"
    r"(?:help me\s+)?"
    r"(?:find|compute|calculate|evaluate|determine|work out|what is|what's|whats|"
    r"solve|simplify|factor(?:ize|ise)?|expand|differentiate|integrate|"
    r"take|give me|show me|tell me)?\s*"
    r"(?:the\s+)?"
    r"(?:value of\s+|result of\s+|answer to\s+|solution (?:of|to)\s+|roots? of\s+|zeros? of\s+)?",
    re.IGNORECASE,
)
_TRAILING_NOISE = re.compile(r"[\s?.!]+$")

DEFAULT_VARIABLE = sp.Symbol("x")


class MathParseError(ValueError):
    """Raised when the input cannot be interpreted as a mathematical expression."""


def normalize_text(text: str) -> str:
    """Normalise unicode math glyphs and spoken operators into parser-friendly ASCII."""
    out = text.strip()
    for glyph, replacement in _UNICODE_REPLACEMENTS.items():
        out = out.replace(glyph, replacement)
    for pattern, replacement in _WORD_OPERATORS:
        out = re.sub(pattern, f" {replacement} ", out, flags=re.IGNORECASE)
    out = re.sub(r"\bsquare root of\s+([A-Za-z0-9_.]+|\([^)]*\))", r"sqrt(\1)", out, flags=re.IGNORECASE)
    out = re.sub(r"\bcube root of\s+([A-Za-z0-9_.]+|\([^)]*\))", r"cbrt(\1)", out, flags=re.IGNORECASE)
    out = re.sub(r"\s+", " ", out)
    return out.strip()


def _clean_expression_text(text: str) -> str:
    text = normalize_text(text)
    text = _COMMAND_PREFIXES.sub("", text, count=1)
    text = _TRAILING_NOISE.sub("", text)
    # LaTeX-ish fragments users commonly type
    text = text.replace("\\cdot", "*").replace("\\times", "*").replace("\\div", "/")
    text = re.sub(r"\\frac\{([^}]*)\}\{([^}]*)\}", r"((\1)/(\2))", text)
    text = re.sub(r"\\sqrt\{([^}]*)\}", r"sqrt(\1)", text)
    text = text.replace("\\pi", "pi").replace("\\left", "").replace("\\right", "")
    text = re.sub(r"\\(sin|cos|tan|log|ln|exp)", r"\1", text)
    text = text.replace("{", "(").replace("}", ")")
    return text.strip()


# SymPy constants that students (and language models) routinely use as plain
# variables: ``I`` for interest, ``E`` for energy. When treating them as
# constants makes an equation degenerate we re-parse with these as symbols.
_CONSTANTS_AS_SYMBOLS = {"I": sp.Symbol("I"), "E": sp.Symbol("E")}


def parse_expression(text: str, *, constants_as_symbols: bool = False) -> sp.Expr:
    """Safely parse a single expression. Raises MathParseError on failure."""
    cleaned = _clean_expression_text(text)
    if not cleaned:
        raise MathParseError("Empty expression")
    if _FORBIDDEN_TOKENS.search(cleaned) or not _ALLOWED_CHARS.match(cleaned):
        raise MathParseError(f"Unsupported characters in expression: {text!r}")
    # Prose ("what is the meaning of life") would otherwise parse as a product
    # of single-letter symbols. Short runs such as ``xy`` or ``x1`` are genuine
    # implicit products; anything longer must be a known function/constant.
    for word in _IDENTIFIER.findall(cleaned):
        if len(word) > 3 and word not in _ALLOWED_FUNCTIONS and word not in _ALLOWED_SYMBOL_NAMES:
            raise MathParseError(f"Unknown word {word!r} in expression")
    local_dict = dict(_ALLOWED_FUNCTIONS)
    if constants_as_symbols:
        local_dict.update(_CONSTANTS_AS_SYMBOLS)
    try:
        expr = parse_expr(
            cleaned,
            local_dict=local_dict,
            global_dict=_GLOBAL_DICT,
            transformations=_TRANSFORMATIONS,
            evaluate=True,
        )
    except Exception as exc:  # SymPy raises a wide range of error types here
        raise MathParseError(f"Could not parse {text!r}: {exc}") from exc
    if isinstance(expr, bool):
        raise MathParseError(f"{text!r} is not an expression")
    if not isinstance(expr, sp.Basic):
        raise MathParseError(f"{text!r} did not produce a symbolic expression")
    return expr


def _split_equation(text: str) -> Optional[Tuple[str, str]]:
    """Split ``lhs = rhs`` (a single '=' not part of a comparison operator)."""
    parts = re.split(r"(?<![<>!=])=(?!=)", text)
    if len(parts) == 2:
        return parts[0].strip(), parts[1].strip()
    return None


def parse_equation(text: str) -> sp.Eq:
    split = _split_equation(_clean_expression_text(text))
    if split is None:
        # "roots of x^2 - 4" style: treat as expr = 0
        return sp.Eq(parse_expression(text), 0)
    lhs, rhs = split
    if not rhs:
        raise MathParseError("Equation is missing a right-hand side")
    equation = sp.Eq(parse_expression(lhs), parse_expression(rhs))
    if isinstance(equation, sp.logic.boolalg.BooleanAtom):
        # Both sides are constants. Usually "I" or "E" was meant as a variable
        # (interest, energy), so try again with those as symbols.
        cleaned = _clean_expression_text(text)
        if re.search(r"\b[IE]\b", cleaned):
            equation = sp.Eq(
                parse_expression(lhs, constants_as_symbols=True),
                parse_expression(rhs, constants_as_symbols=True),
            )
        if isinstance(equation, sp.logic.boolalg.BooleanAtom):
            verdict = "true" if equation else "false"
            raise MathParseError(f"Both sides of {text!r} are constants (the statement is {verdict}); there is nothing to solve for")
    return equation


def _pick_variable(exprs: Iterable[sp.Basic], requested: Optional[str] = None) -> sp.Symbol:
    if requested:
        return sp.Symbol(requested)
    symbols: set = set()
    for expr in exprs:
        symbols |= expr.free_symbols
    if not symbols:
        return DEFAULT_VARIABLE
    if DEFAULT_VARIABLE in symbols:
        return DEFAULT_VARIABLE
    # Prefer conventional variable names, then alphabetical order for determinism
    for preferred in ("y", "t", "z", "n", "a"):
        candidate = sp.Symbol(preferred)
        if candidate in symbols:
            return candidate
    return sorted(symbols, key=lambda s: s.name)[0]


class _HumanStr(StrPrinter):
    """Prints 180.000000000000 as 180 and 87.5000000000000 as 87.5."""

    def _print_Float(self, expr):  # noqa: N802
        return _human_float(expr)


class _HumanLatex(LatexPrinter):
    def _print_Float(self, expr):  # noqa: N802
        return _human_float(expr)


def _human_float(value: Any) -> str:
    text = format(float(value), ".10g")
    if "e" in text:
        mantissa, exponent = text.split("e")
        return f"{mantissa}*10^{int(exponent)}"
    return text


def _integer_floats(expr: sp.Basic) -> sp.Basic:
    """1.0*t -> t, 2.0*x**2 -> 2*x**2 (only whole-valued floats are touched)."""
    if not expr.has(sp.Float):
        return expr
    subs = {f: sp.Integer(int(f)) for f in expr.atoms(sp.Float) if abs(float(f)) < 1e15 and float(f).is_integer()}
    return expr.xreplace(subs) if subs else expr


def _fmt(expr: Any) -> str:
    """Plain-text rendering suitable for the chat UI."""
    if isinstance(expr, (list, tuple, set, frozenset, sp.FiniteSet)):
        return ", ".join(_fmt(item) for item in expr)
    return _HumanStr().doprint(_integer_floats(expr)) if isinstance(expr, sp.Basic) else str(expr)


def _latex(expr: Any) -> str:
    try:
        if isinstance(expr, (list, tuple)):
            return ",\\ ".join(_latex(item) for item in expr)
        return _HumanLatex().doprint(_integer_floats(expr)) if isinstance(expr, sp.Basic) else sp.latex(expr)
    except Exception:
        return str(expr)


def _approx(expr: sp.Basic, digits: int = 6) -> Optional[str]:
    """Decimal approximation when the exact result is not already a plain number."""
    try:
        if expr.free_symbols or expr.is_Integer or expr.is_Float or not expr.is_number:
            return None
        if expr.is_Rational and (expr.q & (expr.q - 1)) == 0 and expr.q <= 16:
            # Halves, quarters, ... already read naturally (1/2, 3/4); no need for 0.5.
            return None
        value = sp.N(expr, digits)
        if not value.is_number or value.has(sp.nan):
            return None
        text = sp.sstr(value)
        if "." in text and "e" not in text.lower():
            text = text.rstrip("0").rstrip(".")
        return text if text and text != sp.sstr(expr) else None
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Result model
# --------------------------------------------------------------------------- #


@dataclass
class MathResult:
    problem: str
    problem_type: str
    solution: str
    steps: List[str] = field(default_factory=list)
    solution_latex: str = ""
    confidence: float = 0.9
    method: str = "sympy"
    variable: Optional[str] = None
    result: Any = field(default=None, repr=False)  # raw SymPy object, not serialised
    approximation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "problem": self.problem,
            "problem_type": self.problem_type,
            "solution": self.solution,
            "solution_latex": self.solution_latex,
            "steps": list(self.steps),
            "confidence": self.confidence,
            "method": self.method,
            "variable": self.variable,
            "approximation": self.approximation,
        }


# --------------------------------------------------------------------------- #
# Intent detection
# --------------------------------------------------------------------------- #

_INTENT_PATTERNS: Sequence[Tuple[str, re.Pattern]] = (
    ("limit", re.compile(r"\blim(?:it)?\b", re.IGNORECASE)),
    ("derivative", re.compile(r"\b(derivative|differentiate|d/d[a-z]|diff\b|slope of)", re.IGNORECASE)),
    ("integral", re.compile(r"\b(integral|integrate|antiderivative|area under)", re.IGNORECASE)),
    ("factor", re.compile(r"\bfactor(?:ize|ise|ing)?\b", re.IGNORECASE)),
    ("expand", re.compile(r"\bexpand\b", re.IGNORECASE)),
    ("simplify", re.compile(r"\bsimplif(?:y|ies|ication)\b", re.IGNORECASE)),
    ("solve", re.compile(r"\b(solve|roots?|zeros?|find [a-z]\b|for [a-z]\b)", re.IGNORECASE)),
)


def detect_problem_type(text: str) -> str:
    normalized = normalize_text(text)
    for intent, pattern in _INTENT_PATTERNS:
        if pattern.search(normalized):
            return intent
    if re.search(r"(<=|>=|<|>)", normalized) and "->" not in normalized:
        return "inequality"
    if re.search(r"(?<![<>!=])=(?!=)", normalized):
        # One or more plain equations (systems included)
        return "solve"
    return "evaluate"


# --------------------------------------------------------------------------- #
# Solvers
# --------------------------------------------------------------------------- #


def _requested_variable(text: str) -> Optional[str]:
    match = re.search(r"\b(?:with respect to|w\.?r\.?t\.?|for|in terms of)\s+([A-Za-z])\b", text, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\bd/d([A-Za-z])\b", text)
    if match:
        return match.group(1)
    return None


def _strip_variable_clause(text: str) -> str:
    text = re.sub(r"\b(?:with respect to|w\.?r\.?t\.?|in terms of)\s+[A-Za-z]\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bfor\s+[A-Za-z]\b\s*$", "", text, flags=re.IGNORECASE)
    # "solve for y: 2y - 4 = 10" / "solve for y, 2y = 8"
    text = re.sub(r"\bfor\s+[A-Za-z]\b\s*[:,]\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bd/d[A-Za-z]\b\s*(?:of)?", "", text)
    text = re.sub(r"\b(derivative|differentiate|integral|integrate|antiderivative|limit|lim|simplify|factor(?:ize|ise)?|expand|solve|roots?|zeros?)\b\s*(?:of|the)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^\s*(?:the\s+)?(?:equation|expression|function)?\s*[:,]?\s*", "", text, flags=re.IGNORECASE)
    return text.strip()


def solve_equation(text: str, variable: Optional[str] = None) -> MathResult:
    body = _strip_variable_clause(normalize_text(text))
    var_name = variable or _requested_variable(text)

    # Systems: split on ';' or ' and ' / ',' when every part contains '='
    parts = [p.strip() for p in re.split(r";|\band\b|,", body) if p.strip()]
    if len(parts) > 1 and all(_split_equation(p) for p in parts):
        return _solve_system([parse_equation(p) for p in parts])

    equation = parse_equation(body)
    var = _pick_variable([equation.lhs, equation.rhs], var_name)
    steps = [f"Start with the equation: {_fmt(equation.lhs)} = {_fmt(equation.rhs)}"]

    expr = sp.expand(equation.lhs - equation.rhs)
    if equation.rhs != 0:
        steps.append(f"Move every term to one side: {_fmt(expr)} = 0")

    if expr.is_polynomial(var):
        poly = sp.Poly(expr, var)
        degree = poly.degree()
        factored = sp.factor(expr)
        if degree >= 2 and factored != expr:
            steps.append(f"Factor the left-hand side: {_fmt(factored)} = 0")
        if degree == 2:
            a, b, c = poly.all_coeffs()
            disc = sp.simplify(b**2 - 4 * a * c)
            steps.append(f"This is quadratic (a={_fmt(a)}, b={_fmt(b)}, c={_fmt(c)}); discriminant b^2 - 4ac = {_fmt(disc)}")

    solutions = sp.solve(equation, var, dict=False)
    if isinstance(solutions, dict):
        solutions = [solutions[var]] if var in solutions else list(solutions.values())
    if not isinstance(solutions, (list, tuple)):
        solutions = [solutions]
    solutions = [sp.simplify(s) for s in solutions]

    if not solutions:
        result_text = f"No solution for {var}"
        steps.append(result_text)
        return MathResult(text, "equation", result_text, steps, "", 0.85, variable=var.name, result=[])

    rendered = " or ".join(f"{var} = {_fmt(s)}" for s in solutions)
    steps.append(f"Solve for {var}: {rendered}")

    checks = []
    for s in solutions:
        try:
            residual = sp.simplify((equation.lhs - equation.rhs).subs(var, s))
            checks.append(residual == 0)
        except Exception:
            checks.append(False)
    if checks and all(checks):
        steps.append("Check: substituting each value back into the original equation gives 0 = 0.")
    confidence = 0.97 if checks and all(checks) else 0.8

    approximations = [_approx(s) for s in solutions]
    approx_text = None
    if any(approximations):
        approx_text = ", ".join(f"{var} ≈ {a}" for a in approximations if a)

    return MathResult(
        problem=text,
        problem_type="equation",
        solution=rendered,
        steps=steps,
        solution_latex=",\\ ".join(f"{_latex(var)} = {_latex(s)}" for s in solutions),
        confidence=confidence,
        variable=var.name,
        result=solutions,
        approximation=approx_text,
    )


def _solve_system(equations: List[sp.Eq]) -> MathResult:
    symbols = sorted(set().union(*[eq.free_symbols for eq in equations]), key=lambda s: s.name)
    steps = ["System of equations:"] + [f"  {_fmt(eq.lhs)} = {_fmt(eq.rhs)}" for eq in equations]
    solutions = sp.solve(equations, symbols, dict=True)
    if not solutions:
        steps.append("The system has no solution.")
        return MathResult("; ".join(map(str, equations)), "system", "No solution", steps, "", 0.85, result=[])
    rendered_sets = []
    for sol in solutions:
        rendered_sets.append(", ".join(f"{k} = {_fmt(v)}" for k, v in sorted(sol.items(), key=lambda kv: kv[0].name)))
    rendered = " or ".join(f"({r})" for r in rendered_sets) if len(rendered_sets) > 1 else rendered_sets[0]
    steps.append(f"Solving simultaneously gives: {rendered}")
    return MathResult(
        problem="; ".join(f"{_fmt(eq.lhs)} = {_fmt(eq.rhs)}" for eq in equations),
        problem_type="system",
        solution=rendered,
        steps=steps,
        solution_latex=",\\ ".join(f"{_latex(k)} = {_latex(v)}" for sol in solutions for k, v in sol.items()),
        confidence=0.95,
        result=solutions,
    )


def solve_inequality(text: str) -> MathResult:
    body = _strip_variable_clause(normalize_text(text))
    cleaned = _clean_expression_text(body)
    match = re.match(r"^(.*?)(<=|>=|<|>)(.*)$", cleaned)
    if not match:
        raise MathParseError("Could not find a comparison operator")
    lhs, op, rhs = parse_expression(match.group(1)), match.group(2), parse_expression(match.group(3))
    relation = {"<": sp.Lt, "<=": sp.Le, ">": sp.Gt, ">=": sp.Ge}[op](lhs, rhs)
    var = _pick_variable([lhs, rhs], _requested_variable(text))
    steps = [f"Inequality: {_fmt(relation)}"]
    solution = sp.solve_univariate_inequality(relation, var, relational=True)
    steps.append(f"Solution set for {var}: {_fmt(solution)}")
    return MathResult(text, "inequality", _fmt(solution), steps, _latex(solution), 0.93, variable=var.name, result=solution)


def differentiate(text: str) -> MathResult:
    var_name = _requested_variable(text)
    body = _strip_variable_clause(normalize_text(text))
    expr = parse_expression(body)
    var = _pick_variable([expr], var_name)
    derivative = sp.diff(expr, var)
    simplified = sp.simplify(derivative)
    steps = [
        f"Function: f({var}) = {_fmt(expr)}",
        f"Differentiate with respect to {var}: d/d{var} [{_fmt(expr)}]",
        f"Apply the differentiation rules: f'({var}) = {_fmt(derivative)}",
    ]
    if simplified != derivative:
        steps.append(f"Simplify: f'({var}) = {_fmt(simplified)}")
    return MathResult(text, "derivative", f"f'({var}) = {_fmt(simplified)}", steps, _latex(simplified), 0.97, variable=var.name, result=simplified)


_BOUNDS_PATTERN = re.compile(r"\bfrom\s+(.+?)\s+to\s+(.+?)(?:\s+with respect to\s+[a-z])?\s*$", re.IGNORECASE)


def integrate(text: str) -> MathResult:
    var_name = _requested_variable(text)
    normalized = normalize_text(text)
    lower = upper = None
    bounds = _BOUNDS_PATTERN.search(normalized)
    if bounds:
        lower, upper = parse_expression(bounds.group(1)), parse_expression(bounds.group(2))
        normalized = normalized[: bounds.start()].strip()
    body = _strip_variable_clause(normalized)
    body = re.sub(r"\bd[a-z]\s*$", "", body).strip()  # trailing "dx"
    expr = parse_expression(body)
    var = _pick_variable([expr], var_name)

    antiderivative = sp.integrate(expr, var)
    steps = [f"Integrand: {_fmt(expr)}", f"Integrate with respect to {var}: ∫ {_fmt(expr)} d{var}"]
    if lower is not None and upper is not None:
        value = sp.simplify(sp.integrate(expr, (var, lower, upper)))
        steps.append(f"Antiderivative: F({var}) = {_fmt(antiderivative)}")
        steps.append(f"Evaluate F({_fmt(upper)}) - F({_fmt(lower)}) = {_fmt(value)}")
        return MathResult(
            text, "definite_integral", _fmt(value), steps, _latex(value), 0.97,
            variable=var.name, result=value, approximation=_approx(value),
        )
    steps.append(f"Result: {_fmt(antiderivative)} + C")
    return MathResult(text, "integral", f"{_fmt(antiderivative)} + C", steps, _latex(antiderivative) + " + C", 0.96, variable=var.name, result=antiderivative)


_LIMIT_PATTERN = re.compile(r"\bas\s+([A-Za-z])\s*(?:->|approaches|tends to|goes to)\s*(.+?)\s*$", re.IGNORECASE)


def limit(text: str) -> MathResult:
    normalized = normalize_text(text)
    match = _LIMIT_PATTERN.search(normalized)
    if not match:
        raise MathParseError("A limit needs the form 'limit of f(x) as x -> a'")
    var = sp.Symbol(match.group(1))
    point_text = match.group(2)
    direction = "+-"
    if point_text.endswith("+"):
        direction, point_text = "+", point_text[:-1]
    elif point_text.endswith("-") and len(point_text) > 1 and not point_text[-2].isdigit():
        direction, point_text = "-", point_text[:-1]
    point = parse_expression(point_text)
    body = _strip_variable_clause(normalized[: match.start()])
    expr = parse_expression(body)
    value = sp.limit(expr, var, point, dir=direction if direction != "+-" else "+-")
    steps = [
        f"Expression: {_fmt(expr)}",
        f"Take the limit as {var} -> {_fmt(point)}",
    ]
    try:
        direct = expr.subs(var, point)
        if direct.has(sp.nan, sp.zoo) or direct in (sp.nan, sp.zoo):
            steps.append("Direct substitution is indeterminate, so the limit is evaluated analytically.")
    except Exception:
        pass
    steps.append(f"Limit = {_fmt(value)}")
    return MathResult(text, "limit", _fmt(value), steps, _latex(value), 0.95, variable=var.name, result=value, approximation=_approx(value))


def _rewrite(text: str, kind: str) -> MathResult:
    body = _strip_variable_clause(normalize_text(text))
    expr = parse_expression(body)
    operation = {"simplify": sp.simplify, "factor": sp.factor, "expand": sp.expand}[kind]
    result = operation(expr)
    steps = [f"Original expression: {_fmt(expr)}", f"{kind.capitalize()}: {_fmt(result)}"]
    if result == expr:
        steps.append(f"The expression is already in its {kind if kind != 'simplify' else 'simplest'} form.")
    return MathResult(text, kind, _fmt(result), steps, _latex(result), 0.95, result=result)


def evaluate(text: str) -> MathResult:
    body = _strip_variable_clause(normalize_text(text))
    expr = parse_expression(body)
    if expr.free_symbols:
        simplified = sp.simplify(expr)
        steps = [f"Expression: {_fmt(expr)}"]
        if simplified != expr:
            steps.append(f"Simplified: {_fmt(simplified)}")
        else:
            steps.append("No further simplification is possible without values for the variables.")
        variables = ", ".join(sorted(s.name for s in expr.free_symbols))
        return MathResult(text, "simplify", _fmt(simplified), steps, _latex(simplified), 0.85, variable=variables, result=simplified)

    exact = sp.nsimplify(expr) if expr.is_Float else sp.simplify(expr)
    steps = [f"Expression: {_fmt(expr)}"]
    approx = _approx(exact)
    if approx:
        steps.append(f"Exact value: {_fmt(exact)}")
        steps.append(f"Decimal approximation: {approx}")
    else:
        steps.append(f"Result: {_fmt(exact)}")
    return MathResult(text, "evaluate", _fmt(exact), steps, _latex(exact), 0.98, result=exact, approximation=approx)


# --------------------------------------------------------------------------- #
# Public entry points
# --------------------------------------------------------------------------- #


def solve(problem: str) -> MathResult:
    """Solve a natural-language or symbolic math problem deterministically."""
    if not problem or not problem.strip():
        raise MathParseError("Empty problem")
    problem_type = detect_problem_type(problem)
    try:
        if problem_type == "derivative":
            return differentiate(problem)
        if problem_type == "integral":
            return integrate(problem)
        if problem_type == "limit":
            return limit(problem)
        if problem_type in ("simplify", "factor", "expand"):
            return _rewrite(problem, problem_type)
        if problem_type == "inequality":
            return solve_inequality(problem)
        if problem_type == "solve":
            return solve_equation(problem)
        return evaluate(problem)
    except MathParseError:
        raise
    except Exception as exc:  # SymPy raised something unexpected for this input
        logger.debug("Solver failed for %r: %s", problem, exc)
        raise MathParseError(f"Unable to solve {problem!r}: {exc}") from exc


def _parse_proposed_values(solution_text: str) -> List[sp.Expr]:
    cleaned = normalize_text(solution_text)
    cleaned = re.sub(r"\b[a-zA-Z]\s*=\s*", "", cleaned)
    values = []
    for part in re.split(r",|\bor\b|\band\b|;", cleaned):
        part = part.strip()
        if part:
            values.append(parse_expression(part))
    return values


def verify(problem: str, proposed_solution: str) -> Dict[str, Any]:
    """
    Check a proposed solution against the engine's own answer.

    Returns a dict with ``is_correct``, ``confidence``, ``feedback`` and the
    engine's ``expected`` answer so the UI can show the discrepancy.
    """
    expected = solve(problem)
    feedback: str
    is_correct = False

    try:
        if expected.problem_type in ("equation",):
            proposed = _parse_proposed_values(proposed_solution)
            expected_set = {sp.simplify(v) for v in expected.result}
            proposed_set = set()
            for value in proposed:
                proposed_set.add(sp.simplify(value))
            is_correct = bool(proposed_set) and all(
                any(sp.simplify(p - e) == 0 for e in expected_set) for p in proposed_set
            ) and len(proposed_set) == len(expected_set)
            if is_correct:
                feedback = "Correct: every proposed value satisfies the equation and no solutions are missing."
            elif proposed_set and all(any(sp.simplify(p - e) == 0 for e in expected_set) for p in proposed_set):
                feedback = f"Partially correct: the values given are valid, but the full solution is {expected.solution}."
            else:
                feedback = f"Incorrect: the equation's solution is {expected.solution}."
        elif expected.problem_type in ("inequality", "system"):
            is_correct = normalize_text(proposed_solution).replace(" ", "") == expected.solution.replace(" ", "")
            feedback = "Correct." if is_correct else f"Expected {expected.solution}."
        else:
            proposed_text = re.sub(r"^\s*(?:f'\([a-z]\)|[a-zA-Z]'?)\s*=\s*", "", normalize_text(proposed_solution))
            proposed_text = re.sub(r"\+\s*C\s*$", "", proposed_text, flags=re.IGNORECASE)
            proposed_expr = parse_expression(proposed_text)
            expected_expr = expected.result
            diff = sp.simplify(proposed_expr - expected_expr)
            if expected.problem_type == "integral":
                # Antiderivatives may differ by a constant
                is_correct = diff.is_constant()
            else:
                is_correct = diff == 0
            if not is_correct and not diff.free_symbols:
                is_correct = abs(complex(sp.N(diff))) < 1e-9
            feedback = "Correct: the proposed answer is equivalent to the computed result." if is_correct else f"Incorrect: the computed result is {expected.solution}."
    except MathParseError as exc:
        feedback = f"Could not interpret the proposed solution ({exc}). Expected {expected.solution}."
    except Exception as exc:
        logger.debug("Verification failed: %s", exc)
        feedback = f"Verification could not be completed. Expected {expected.solution}."

    return {
        "is_correct": bool(is_correct),
        "confidence": 0.95 if is_correct else 0.9,
        "feedback": feedback,
        "expected": expected.solution,
        "expected_steps": expected.steps,
        "alternative_solutions": [] if is_correct else [expected.solution],
    }
