"""
Runtime-editable language model configuration.

Which language model answers free-form questions and writes practice problems
is a user choice that can change mid-session (e.g. "use my local model, but
fall back to OpenRouter when it is not loaded"). This module owns that choice:

* ``mode``   -- ``local`` (only a model loaded in this process), ``remote``
                (only the configured API), or ``auto`` (local when loaded,
                otherwise remote).
* ``remote`` -- provider preset, base URL, API key, model, timeout.

Defaults come from environment variables / ``.env`` (``LLM_API_*``, plus
``OPENROUTER_API_KEY`` as a convenience); anything the user changes in the app
is persisted to ``<data_dir>/llm_config.json`` and wins over the environment
on the next start.
"""

from __future__ import annotations

import json
import logging
import os
import stat
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from services.llm_client import PROVIDER_PRESETS, preset_for_url

logger = logging.getLogger(__name__)

MODES = ("auto", "local", "remote")
CONFIG_FILENAME = "llm_config.json"


@dataclass
class RemoteLLMSettings:
    preset: str = "openrouter"
    base_url: str = PROVIDER_PRESETS["openrouter"]["base_url"]
    api_key: Optional[str] = None
    model: str = ""
    timeout_seconds: float = 60.0

    @property
    def configured(self) -> bool:
        """Enough information to attempt a request."""
        return bool(self.base_url and self.model)

    def public(self) -> Dict[str, Any]:
        """Serialisable view that never leaks the key."""
        return {
            "preset": self.preset,
            "base_url": self.base_url,
            "model": self.model,
            "timeout_seconds": self.timeout_seconds,
            "has_api_key": bool(self.api_key),
            "api_key_hint": mask_key(self.api_key),
            "configured": self.configured,
        }


@dataclass
class LLMConfig:
    mode: str = "auto"
    remote: RemoteLLMSettings = field(default_factory=RemoteLLMSettings)


def mask_key(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    if len(key) <= 8:
        return "•" * len(key)
    return f"{key[:4]}…{key[-4:]}"


class LLMConfigStore:
    """Load/merge/persist :class:`LLMConfig`."""

    def __init__(self, settings):
        self.settings = settings
        self.path = Path(settings.data_dir) / CONFIG_FILENAME
        self.config = self._load()

    # ------------------------------------------------------------------ #
    # Loading
    # ------------------------------------------------------------------ #

    def _from_environment(self) -> LLMConfig:
        s = self.settings
        remote = RemoteLLMSettings(timeout_seconds=float(s.llm_api_timeout_seconds))
        if s.llm_api_base_url:
            remote.base_url = s.llm_api_base_url
            remote.preset = preset_for_url(s.llm_api_base_url)
            remote.api_key = s.llm_api_key
            remote.model = s.llm_api_model
        elif s.openrouter_api_key:
            remote.preset = "openrouter"
            remote.base_url = PROVIDER_PRESETS["openrouter"]["base_url"]
            remote.api_key = s.openrouter_api_key
            remote.model = s.llm_api_model if s.llm_api_model != "gpt-4o-mini" else PROVIDER_PRESETS["openrouter"]["default_model"]
        else:
            remote.api_key = s.llm_api_key or s.openrouter_api_key
        mode = (s.llm_mode or "auto").lower()
        return LLMConfig(mode=mode if mode in MODES else "auto", remote=remote)

    def _load(self) -> LLMConfig:
        config = self._from_environment()
        if not self.path.exists():
            return config
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            logger.warning("Ignoring unreadable %s: %s", self.path, exc)
            return config
        if not isinstance(data, dict):
            return config
        mode = str(data.get("mode", config.mode)).lower()
        if mode in MODES:
            config.mode = mode
        remote = data.get("remote") or {}
        if isinstance(remote, dict):
            r = config.remote
            r.preset = str(remote.get("preset", r.preset))
            r.base_url = str(remote.get("base_url", r.base_url)).rstrip("/")
            if "api_key" in remote:
                r.api_key = remote.get("api_key") or None
            r.model = str(remote.get("model", r.model))
            try:
                r.timeout_seconds = float(remote.get("timeout_seconds", r.timeout_seconds))
            except (TypeError, ValueError):
                pass
            if r.preset not in PROVIDER_PRESETS:
                r.preset = preset_for_url(r.base_url)
        return config

    # ------------------------------------------------------------------ #
    # Updating
    # ------------------------------------------------------------------ #

    def update(
        self,
        *,
        mode: Optional[str] = None,
        preset: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        clear_api_key: bool = False,
        model: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
    ) -> LLMConfig:
        cfg = self.config
        r = cfg.remote
        if mode is not None:
            mode = mode.lower()
            if mode not in MODES:
                raise ValueError(f"mode must be one of {', '.join(MODES)}")
            cfg.mode = mode
        if preset is not None:
            if preset not in PROVIDER_PRESETS:
                raise ValueError(f"unknown provider preset '{preset}'")
            if preset != r.preset:
                # Switching provider: take its default URL/model unless the caller overrides them.
                r.preset = preset
                r.base_url = PROVIDER_PRESETS[preset]["base_url"]
                if model is None:
                    r.model = PROVIDER_PRESETS[preset]["default_model"]
        if base_url is not None:
            base_url = base_url.strip().rstrip("/")
            if base_url and not base_url.lower().startswith(("http://", "https://")):
                raise ValueError("base_url must start with http:// or https://")
            r.base_url = base_url
            if preset is None and r.preset != "custom" and preset_for_url(base_url) != r.preset:
                r.preset = preset_for_url(base_url)
        if clear_api_key:
            r.api_key = None
        elif api_key is not None:
            api_key = api_key.strip()
            if api_key:
                r.api_key = api_key
        if model is not None:
            r.model = model.strip()
        if timeout_seconds is not None:
            if not 1 <= timeout_seconds <= 600:
                raise ValueError("timeout_seconds must be between 1 and 600")
            r.timeout_seconds = float(timeout_seconds)
        self.save()
        return cfg

    def reset(self) -> LLMConfig:
        try:
            self.path.unlink(missing_ok=True)
        except OSError as exc:
            logger.error("Could not remove %s: %s", self.path, exc)
        self.config = self._from_environment()
        return self.config

    def save(self) -> None:
        payload = {"mode": self.config.mode, "remote": asdict(self.config.remote)}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            if sys.platform != "win32":
                os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
            os.replace(tmp, self.path)
        except OSError as exc:
            logger.error("Could not persist LLM config to %s: %s", self.path, exc)

    # ------------------------------------------------------------------ #
    # Views
    # ------------------------------------------------------------------ #

    def public(self) -> Dict[str, Any]:
        return {
            "mode": self.config.mode,
            "remote": self.config.remote.public(),
            "presets": [
                {"id": pid, **{k: v for k, v in preset.items()}} for pid, preset in PROVIDER_PRESETS.items()
            ],
            "config_path": str(self.path),
        }
