"""
autopilot/config.py — Configuration manager for AutoPilot
=========================================================

Manages ~/.autopilot/config.json

Primary provider: Azure AI Foundry
The Foundry endpoint hosts the 3-agent workflow (Planner → Researcher → Writer)
that converts natural language tasks into executable shell commands.
"""

from __future__ import annotations

import json
import platform
from pathlib import Path
from typing import Any


AUTOPILOT_HOME = Path.home() / ".autopilot"
CONFIG_FILE = AUTOPILOT_HOME / "config.json"


def detect_os() -> str:
    """Detect the current operating system."""
    system = platform.system().lower()
    if system == "windows":
        return "Windows (PowerShell)"
    elif system == "darwin":
        return "macOS (zsh/bash)"
    else:
        return "Linux (bash)"


def detect_shell() -> str:
    """Detect the current shell type."""
    system = platform.system().lower()
    if system == "windows":
        return "powershell"
    elif system == "darwin":
        return "zsh"
    else:
        return "bash"


class Config:
    """
    Configuration wrapper for AutoPilot.

    Stores Azure AI Foundry endpoint, OS info, and preferences
    in ~/.autopilot/config.json.

    Usage
    -----
        cfg = Config()
        cfg.endpoint        # → "https://..."
        cfg.os_name         # → "Windows (PowerShell)"
        cfg.set("endpoint", "https://...")
        cfg.save()
    """

    def __init__(self) -> None:
        AUTOPILOT_HOME.mkdir(parents=True, exist_ok=True)
        self._data: dict[str, Any] = {}
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        if CONFIG_FILE.exists():
            try:
                self._data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def save(self) -> None:
        CONFIG_FILE.write_text(json.dumps(self._data, indent=2), encoding="utf-8")

    # ── Read / Write ──────────────────────────────────────────────────────────

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def is_configured(self) -> bool:
        """Returns True if the Foundry endpoint has been set."""
        return bool(self._data.get("endpoint"))

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def endpoint(self) -> str:
        """Azure AI Foundry project endpoint."""
        return self._data.get("endpoint", "")

    @property
    def workflow_name(self) -> str:
        """Name of the Foundry workflow (default: autopilot)."""
        return self._data.get("workflow_name", "autopilot")

    @property
    def workflow_version(self) -> str:
        """Version of the Foundry workflow."""
        return self._data.get("workflow_version", "1")

    @property
    def os_name(self) -> str:
        """Detected operating system name."""
        return self._data.get("os_name", detect_os())

    @property
    def shell(self) -> str:
        """Detected shell type."""
        return self._data.get("shell", detect_shell())

    @property
    def auto_execute_safe(self) -> bool:
        """Whether to auto-execute 'safe' commands without asking."""
        return self._data.get("auto_execute_safe", False)
