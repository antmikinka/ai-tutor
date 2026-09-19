"""
VARK learning-style profile (Visual, Aural, Read/write, Kinesthetic).

The scores come from the VARK questionnaire (each mode 0-16). They are a
*preference*, not a limitation, so the tutor uses them to choose how to
present material: what the language model is asked to include, which hints
come first, and which UI affordances are emphasised.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

MODES = ("visual", "aural", "read_write", "kinesthetic")
MODE_LABELS = {"visual": "Visual", "aural": "Aural", "read_write": "Read/write", "kinesthetic": "Kinesthetic"}
MAX_SCORE = 16


def _stepping_distance(total: int) -> int:
    """VARK's rule for how close a mode must be to the top score to count as preferred."""
    if total <= 16:
        return 1
    if total <= 22:
        return 2
    if total <= 26:
        return 3
    return 4


@dataclass(frozen=True)
class LearningStyle:
    visual: int = 0
    aural: int = 0
    read_write: int = 0
    kinesthetic: int = 0

    @classmethod
    def from_mapping(cls, data: Optional[Mapping[str, Any]]) -> Optional["LearningStyle"]:
        """Build from a request payload; returns None when nothing meaningful was provided."""
        if not data:
            return None
        values: Dict[str, int] = {}
        aliases = {"read_write": ("read_write", "readWrite", "read", "R"), "visual": ("visual", "V"), "aural": ("aural", "A"), "kinesthetic": ("kinesthetic", "K")}
        for mode in MODES:
            raw = next((data[k] for k in aliases[mode] if k in data), 0)
            try:
                values[mode] = max(0, min(MAX_SCORE, int(raw or 0)))
            except (TypeError, ValueError):
                values[mode] = 0
        style = cls(**values)
        return style if style.is_set else None

    @property
    def is_set(self) -> bool:
        return any(getattr(self, m) > 0 for m in MODES)

    @property
    def total(self) -> int:
        return sum(getattr(self, m) for m in MODES)

    def preferred(self) -> List[str]:
        if not self.is_set:
            return []
        top = max(getattr(self, m) for m in MODES)
        step = _stepping_distance(self.total)
        return [m for m in MODES if getattr(self, m) >= top - step and getattr(self, m) > 0]

    def label(self) -> str:
        prefs = self.preferred()
        if not prefs:
            return "Not set"
        if len(prefs) == 4:
            return "Multimodal (VARK)"
        if len(prefs) >= 2:
            return "Multimodal (" + ", ".join(MODE_LABELS[m] for m in prefs) + ")"
        return MODE_LABELS[prefs[0]]

    def prompt_hint(self) -> str:
        """One paragraph for the language model describing how to present material."""
        prefs = self.preferred()
        if not prefs:
            return ""
        parts = ["The learner's VARK profile prefers: " + ", ".join(MODE_LABELS[m] for m in prefs) + "."]
        if "visual" in prefs:
            parts.append(
                "Visual: include a \"sketch\" field - one sentence describing a diagram, graph, bar model or labelled "
                "picture the learner should draw on their whiteboard to see the structure of the problem."
            )
        if "read_write" in prefs:
            parts.append("Read/write: make hints precise, in complete sentences, and name the quantities explicitly (\"Let m be ...\").")
        if "kinesthetic" in prefs:
            parts.append(
                "Kinesthetic: use a concrete, realistic scenario and make the first hint an action - try a specific "
                "number, build a small table of values, or act the situation out - before giving the set-up."
            )
        if "aural" in prefs:
            parts.append("Aural: phrase one hint as something the learner could say out loud to explain the situation to a friend.")
        return " ".join(parts)

    def to_dict(self) -> Dict[str, Any]:
        return {
            **{m: getattr(self, m) for m in MODES},
            "preferred": self.preferred(),
            "label": self.label(),
        }
