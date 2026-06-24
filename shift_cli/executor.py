"""
shift_cli/executor.py — Safe command executor
==============================================

Takes the Writer Agent's JSON execution plan and runs commands
on the real terminal with safety checks.

Risk levels:
  - safe:      no data loss, fully reversible (mkdir, ls, pip install)
  - moderate:  changes system state but reversible (apt install, chmod)
  - dangerous: permanent/destructive (rm -rf, dd, mkfs, sudo rm)
"""

from __future__ import annotations

import platform
import subprocess
import time
from typing import Any

# Commands that should NEVER be auto-executed
DANGEROUS_PATTERNS = [
    "rm -rf", "rm -r /", "rmdir /s",
    "del /f /s /q", "format ",
    "dd if=", "mkfs", "fdisk",
    ":(){ :|:& };:",  # fork bomb
    "> /dev/sda", "chmod 777 /",
    "curl | sh", "curl | bash",
    "wget | sh", "wget | bash",
]


def is_dangerous(command: str) -> bool:
    """Check if a command matches known dangerous patterns."""
    cmd_lower = command.lower().strip()
    return any(pattern in cmd_lower for pattern in DANGEROUS_PATTERNS)


def execute_plan(writer_json: dict[str, Any], shell: str | None = None) -> list[dict[str, Any]]:
    """
    Execute the Writer Agent's final command plan.

    Args:
        writer_json: The parsed JSON from the Writer Agent containing
                     'final_commands' list with step_number, command,
                     explanation, and risk fields.
        shell: The target shell program to execute commands with (e.g. 'powershell', 'bash')

    Returns:
        List of result dicts with command, success, output, error, time.
    """
    if shell is None:
        from shift_cli.config import detect_shell
        shell = detect_shell()

    commands = writer_json.get("final_commands", [])
    results: list[dict[str, Any]] = []
    current_cwd = None
    cwd_stack: list[str] = []

    for item in commands:
        cmd = item.get("command", "")
        risk = item.get("risk", "safe")

        # Override risk if we detect dangerous patterns
        if is_dangerous(cmd):
            risk = "dangerous"

        if risk == "dangerous":
            results.append({
                "step_number": item.get("step_number", 0),
                "command": cmd,
                "success": False,
                "output": "",
                "error": "BLOCKED — dangerous command. Skipped for safety.",
                "time": 0.0,
                "risk": risk,
                "blocked": True,
            })
            continue

        # Determine shell
        use_shell = True
        shell_args = cmd
        if shell == "powershell":
            use_shell = False
            shell_args = ["powershell.exe", "-Command", cmd]
        elif platform.system().lower() != "windows":
            use_shell = False
            shell_args = ["/bin/bash", "-c", cmd]

        # Check for directory changes
        cmd_stripped = cmd.strip()
        cmd_parts = cmd_stripped.split(None, 1)

        is_cd = False
        is_pushd = False
        is_popd = False
        target = ""

        if cmd_parts:
            lower_cmd = cmd_parts[0].lower()
            target = cmd_parts[1].strip() if len(cmd_parts) > 1 else ""
            if (target.startswith('"') and target.endswith('"')) or (target.startswith("'") and target.endswith("'")):
                target = target[1:-1]

            if lower_cmd in ("cd", "chdir", "set-location", "sl"):
                is_cd = True
            elif cmd_stripped == "cd.." or cmd_stripped.startswith("cd.. "):
                is_cd = True
                target = ".."
            elif lower_cmd == "pushd":
                is_pushd = True
            elif lower_cmd == "popd":
                is_popd = True

        proposed_cwd = current_cwd
        proposed_stack = list(cwd_stack)

        if is_cd or is_pushd or is_popd:
            import os
            from pathlib import Path
            base_path = Path(current_cwd) if current_cwd else Path.cwd()

            if is_cd:
                if target:
                    target_expanded = os.path.expanduser(os.path.expandvars(target))
                    try:
                        proposed_cwd = str((base_path / target_expanded).resolve())
                    except Exception:
                        proposed_cwd = str((base_path / target_expanded).absolute())
                else:
                    if platform.system().lower() != "windows":
                        proposed_cwd = str(Path.home())
            elif is_pushd:
                if target:
                    target_expanded = os.path.expanduser(os.path.expandvars(target))
                    try:
                        resolved_target = str((base_path / target_expanded).resolve())
                    except Exception:
                        resolved_target = str((base_path / target_expanded).absolute())
                    proposed_stack.append(current_cwd if current_cwd else str(Path.cwd()))
                    proposed_cwd = resolved_target
            elif is_popd:
                if proposed_stack:
                    proposed_cwd = proposed_stack.pop()

        start = time.time()
        try:
            result = subprocess.run(
                shell_args,
                shell=use_shell,
                cwd=current_cwd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            taken = round(time.time() - start, 2)
            success = result.returncode == 0

            if success:
                current_cwd = proposed_cwd
                cwd_stack = proposed_stack

            results.append({
                "step_number": item.get("step_number", 0),
                "command": cmd,
                "success": success,
                "output": result.stdout.strip(),
                "error": result.stderr.strip(),
                "time": taken,
                "risk": risk,
                "blocked": False,
            })
        except subprocess.TimeoutExpired:
            results.append({
                "step_number": item.get("step_number", 0),
                "command": cmd,
                "success": False,
                "output": "",
                "error": "Command timed out after 60 seconds.",
                "time": 60.0,
                "risk": risk,
                "blocked": False,
            })
        except Exception as exc:
            results.append({
                "step_number": item.get("step_number", 0),
                "command": cmd,
                "success": False,
                "output": "",
                "error": str(exc),
                "time": round(time.time() - start, 2),
                "risk": risk,
                "blocked": False,
            })

    return results
