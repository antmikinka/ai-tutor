"""
Optional heavy dependencies.

The backend must start (and the SymPy solver must work) on a machine that has
none of the ML stack installed. Every module that needs ``torch``,
``transformers``, ``soundfile``, ``librosa`` or ``psutil`` imports them from
here so that a missing package degrades a single feature instead of crashing
the whole server at import time.
"""

from __future__ import annotations

import importlib
import logging
from types import ModuleType
from typing import Optional

logger = logging.getLogger(__name__)


def optional_import(name: str) -> Optional[ModuleType]:
    """Import ``name`` if it is installed, otherwise return ``None``."""
    try:
        return importlib.import_module(name)
    except Exception as exc:  # ImportError, OSError for broken CUDA builds, ...
        logger.debug("Optional dependency %r unavailable: %s", name, exc)
        return None


torch = optional_import("torch")
transformers = optional_import("transformers")
soundfile = optional_import("soundfile")
librosa = optional_import("librosa")
psutil = optional_import("psutil")

HAS_TORCH = torch is not None
HAS_TRANSFORMERS = transformers is not None
HAS_SOUNDFILE = soundfile is not None
HAS_LIBROSA = librosa is not None
HAS_PSUTIL = psutil is not None
HAS_ML_STACK = HAS_TORCH and HAS_TRANSFORMERS


def cuda_available() -> bool:
    return bool(HAS_TORCH and torch.cuda.is_available())


def require(module: Optional[ModuleType], name: str, feature: str) -> ModuleType:
    """Return ``module`` or raise a clear error explaining which feature needs it."""
    if module is None:
        raise RuntimeError(
            f"{feature} requires the optional dependency '{name}'. "
            f"Install it with: pip install {name}"
        )
    return module


def ml_stack_status() -> dict:
    return {
        "torch": HAS_TORCH,
        "transformers": HAS_TRANSFORMERS,
        "soundfile": HAS_SOUNDFILE,
        "librosa": HAS_LIBROSA,
        "psutil": HAS_PSUTIL,
        "cuda": cuda_available(),
    }
