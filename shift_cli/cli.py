"""
shift_cli/cli.py — Shift_CLI command-line interface
=====================================================

Entry point: shift_cli = "shift_cli.cli:main"

After  pip install shift-cli  →  run  shift_cli

Features
--------
  - First-run setup wizard (Azure AI Foundry endpoint)
  - OS auto-detection (Windows/macOS/Linux)
  - Human-in-the-loop clarifying questions before execution
  - 3-agent pipeline via Azure AI Foundry (Planner → Researcher → Writer)
  - Risk-aware command execution (safe/moderate/dangerous)
  - Persistent command history (~/.shift_cli/history.db)
  - Interactive REPL with Rich terminal UI
"""

from __future__ import annotations

import argparse
import asyncio
import platform
import sys
from datetime import datetime
from pathlib import Path

# ── Windows UTF-8 ─────────────────────────────────────────────────────────────
if sys.platform == "win32" and "pytest" not in sys.modules:
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# ── Path setup ────────────────────────────────────────────────────────────────
_CLI_DIR = Path(__file__).resolve().parent
_ROOT = _CLI_DIR.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# ── Load .env ─────────────────────────────────────────────────────────────────
from dotenv import load_dotenv

load_dotenv(Path.cwd() / ".env", override=False)
load_dotenv(Path.home() / ".shift_cli" / ".env", override=False)

# ── Silence noisy loggers ─────────────────────────────────────────────────────
import warnings

warnings.filterwarnings("ignore")
import logging

for _log in ("httpx", "azure", "openai", "urllib3"):
    logging.getLogger(_log).setLevel(logging.ERROR)

# ── Rich ──────────────────────────────────────────────────────────────────────
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table

console = Console(highlight=False)

# ── Color palette ─────────────────────────────────────────────────────────────
C_RULE   = "grey46"
C_TITLE  = "bold white"
C_DIM    = "grey46"
C_OK     = "green3"
C_WARN   = "yellow3"
C_ERR    = "red3"
C_LABEL  = "white"
C_ACCENT = "steel_blue1"
C_BORDER = "grey30"
C_SAFE   = "green3"
C_MOD    = "yellow3"
C_DANGER = "red3"

# ── Imports ───────────────────────────────────────────────────────────────────
from shift_cli.config import Config, detect_os, detect_shell
from shift_cli.memory.store import MemoryStore

# ── UI helpers ────────────────────────────────────────────────────────────────

def _rule(title: str = "") -> None:
    if title:
        console.print(Rule(f"[{C_DIM}]{title}[/]", style=C_RULE))
    else:
        console.print(Rule(style=C_RULE))


def _p(msg: str, indent: int = 2) -> None:
    console.print(" " * indent + msg)


def _blank() -> None:
    console.print()


def _ok(msg: str) -> None:
    _p(f"[{C_OK}]{msg}[/]")


def _warn(msg: str) -> None:
    _p(f"[{C_WARN}]{msg}[/]")


def _err(msg: str) -> None:
    _p(f"[{C_ERR}]{msg}[/]")


def _dim(msg: str) -> None:
    _p(f"[{C_DIM}]{msg}[/]")


def _ask(prompt_text: str, password: bool = False) -> str:
    _blank()
    if password:
        import getpass
        console.print(f"  [{C_ACCENT}]{prompt_text}[/]", end="")
        try:
            return getpass.getpass("  ").strip()
        except Exception:
            return ""
    try:
        return console.input(f"  [{C_ACCENT}]{prompt_text}[/]  ").strip()
    except (KeyboardInterrupt, EOFError):
        raise


def _risk_color(risk: str) -> str:
    """Return Rich color for a risk level."""
    return {"safe": C_SAFE, "moderate": C_MOD, "dangerous": C_DANGER}.get(risk, C_DIM)


def _risk_icon(risk: str) -> str:
    """Return icon for a risk level."""
    return {"safe": "[green3]●[/]", "moderate": "[yellow3]▲[/]", "dangerous": "[red3]■[/]"}.get(
        risk, "[grey46]○[/]"
    )


# ── Banner ────────────────────────────────────────────────────────────────────

def _banner() -> None:
    _blank()
    console.print(
        f"  [{C_TITLE}]A U T O P I L O T[/]   "
        f"[{C_DIM}]— AI-Powered Terminal Automation[/]"
    )
    _p(f"[{C_DIM}]{'─' * 54}[/]")
    _blank()


# ── Setup wizard ──────────────────────────────────────────────────────────────

async def run_setup(cfg: Config, *, force: bool = False) -> None:
    """
    Interactive setup wizard. Runs on first install or `shift_cli setup`.
    Saves endpoint and OS info to ~/.shift_cli/config.json.
    """
    _rule("Setup")
    _blank()

    if not force and cfg.is_configured():
        _p(f"[{C_LABEL}]Shift_CLI is already configured.[/]")
        _dim(f"Endpoint : {cfg.endpoint[:60]}...")
        _dim(f"OS       : {cfg.os_name}")
        _blank()
        change = _ask("Reconfigure?  [y/N]  >")
        if change.lower() not in ("y", "yes"):
            return

    _blank()
    _p(f"[{C_LABEL}]Shift_CLI uses Azure AI Foundry to run its 3-agent pipeline.[/]")
    _dim("You'll need your Azure AI Foundry project endpoint.")
    _dim("Get it from: Azure AI Foundry portal → your project → Overview")
    _blank()

    # Endpoint
    ep = _ask("Azure AI Foundry project endpoint  >")
    if ep:
        cfg.set("endpoint", ep.strip())
    else:
        _err("No endpoint provided. You can set it later with 'shift_cli setup'.")
        return

    # Workflow name
    _blank()
    _dim("The default workflow name is 'shift_cli'.")
    wf = _ask("Workflow name  (Enter = shift_cli)  >")
    if wf:
        cfg.set("workflow_name", wf.strip())

    # OS detection
    _blank()
    detected = detect_os()
    _p(f"[{C_LABEL}]Detected OS: {detected}[/]")
    _dim("Commands will be generated for this OS.")
    override = _ask(f"Override OS?  (Enter = {detected})  >")
    if override:
        cfg.set("os_name", override.strip())
    else:
        cfg.set("os_name", detected)

    cfg.set("shell", detect_shell())
    cfg.save()
    _blank()
    _ok(f"Setup complete.  Endpoint: {cfg.endpoint[:50]}...  |  OS: {cfg.os_name}")
    _blank()


# ── Session greeting ──────────────────────────────────────────────────────────

def _greet(memory: MemoryStore, cfg: Config) -> None:
    total = memory.total_task_count()
    session_no = memory.session_number()
    now_str = datetime.now().strftime("%A, %d %B %Y  |  %H:%M")

    session_line = f"Session {session_no}  |  {now_str}  |  {cfg.os_name}"
    _p(f"[{C_DIM}]{session_line}[/]")
    _blank()

    if total > 0:
        recent = memory.get_recent_tasks(3)
        _dim(f"Your history spans {total} {'task' if total == 1 else 'tasks'}.")
        if recent:
            _dim(f"Last task: \"{recent[0]['task'][:70]}\"")
    _blank()


# ── Human-in-the-loop ─────────────────────────────────────────────────────────

async def _run_hitl(task: str, memory: MemoryStore, cfg: Config) -> str:
    """Ask clarifying questions before running the pipeline."""
    _blank()
    _rule("Task received")
    _blank()
    _p(f"[{C_LABEL}]Before generating commands, a few clarifying questions.[/]")
    _dim("Your answers help produce better, more accurate commands.")
    _blank()

    memory_ctx = memory.build_context_string() if not memory.is_first_run() else ""

    with console.status(
        f"  [{C_DIM}]Preparing questions...[/]",
        spinner="line", spinner_style=C_DIM,
    ):
        from shift_cli.hitl.questioner import generate_questions
        questions = await generate_questions(
            task, os_context=cfg.os_name,
            memory_context=memory_ctx,
            cwd_context=str(Path.cwd()),
            cfg=cfg,
        )

    if not questions:
        return ""

    qa_pairs: list[str] = []
    for i, q_text in enumerate(questions, 1):
        _rule(f"Question {i} of {len(questions)}")
        _blank()
        _p(f"[{C_LABEL}]{q_text}[/]")
        try:
            ans = _ask(">")
        except (KeyboardInterrupt, EOFError):
            ans = ""
        if ans:
            qa_pairs.append(f"Q: {q_text}\nA: {ans}")
        else:
            _dim("(skipped)")

    _blank()
    _rule()
    _blank()
    _dim("Understood. Dispatching the agent pipeline now.")
    _blank()

    if not qa_pairs:
        return ""
    return (
        "=== USER CLARIFICATIONS ===\n"
        + "\n\n".join(qa_pairs)
        + "\n=== END CLARIFICATIONS ==="
    )


# ── Display execution plan ────────────────────────────────────────────────────

def _display_plan(writer_json: dict) -> None:
    """Display the Writer Agent's execution plan in a rich table."""
    task = writer_json.get("task", "")
    summary = writer_json.get("summary", "")
    overall_risk = writer_json.get("overall_risk", "safe")
    warnings = writer_json.get("warnings", [])
    commands = writer_json.get("final_commands", [])
    total = writer_json.get("total_commands", len(commands))
    est_time = writer_json.get("estimated_time_seconds", 0)

    _blank()
    _rule("Execution Plan")
    _blank()

    # Summary
    if summary:
        console.print(Panel(
            summary,
            title=f"[{C_LABEL}]Summary[/]",
            border_style=C_BORDER,
            padding=(0, 2),
        ))
        _blank()

    # Overall risk
    risk_col = _risk_color(overall_risk)
    _p(
        f"[{C_LABEL}]Overall Risk:[/] [{risk_col}]{overall_risk.upper()}[/]   "
        f"[{C_DIM}]|  {total} commands  |  ~{est_time}s estimated[/]"
    )
    _blank()

    # Warnings
    if warnings:
        for w in warnings:
            _warn(f"⚠  {w}")
        _blank()

    # Command table
    table = Table(box=box.ROUNDED, border_style=C_BORDER, show_lines=True)
    table.add_column("#", style=C_DIM, width=3, justify="center")
    table.add_column("Command", style=C_LABEL, min_width=30)
    table.add_column("What it does", style=C_DIM, min_width=20)
    table.add_column("Risk", width=10, justify="center")

    for cmd in commands:
        risk = cmd.get("risk", "safe")
        risk_icon = _risk_icon(risk)
        table.add_row(
            str(cmd.get("step_number", "")),
            f"[bold]{cmd.get('command', '')}[/bold]",
            cmd.get("explanation", ""),
            f"{risk_icon} {risk}",
        )

    console.print(table)
    _blank()


# ── Execute commands with confirmation ────────────────────────────────────────

async def _execute_with_confirmation(
    writer_json: dict, memory: MemoryStore, cfg: Config, task: str,
) -> None:
    """Ask for confirmation then execute commands."""
    from shift_cli.executor import execute_plan

    commands = writer_json.get("final_commands", [])
    requires_confirm = writer_json.get("requires_confirmation", False)
    overall_risk = writer_json.get("overall_risk", "safe")

    if not commands:
        _err("No commands to execute.")
        return

    # Always ask for confirmation
    if requires_confirm or overall_risk == "dangerous":
        _warn("This plan contains risky commands.")
        for w in writer_json.get("warnings", []):
            _warn(f"  - {w}")
        _blank()

    confirm = _ask("Execute all commands?  [y/N/step]  >")

    if confirm.lower() == "step":
        # Step-by-step execution
        await _execute_step_by_step(writer_json, memory, cfg, task)
        return
    elif confirm.lower() not in ("y", "yes"):
        _dim("Cancelled. No commands were executed.")
        return

    # Execute all at once
    _blank()
    _rule("Executing")
    _blank()

    results = []
    with console.status(
        f"  [{C_DIM}]Running commands...[/]",
        spinner="line", spinner_style=C_DIM,
    ):
        loop = asyncio.get_running_loop()
        results = await loop.run_in_executor(None, execute_plan, writer_json, cfg.shell)

    _display_results(results)
    _save_results(task, writer_json, results, memory, cfg)


async def _execute_step_by_step(
    writer_json: dict, memory: MemoryStore, cfg: Config, task: str,
) -> None:
    """Execute commands one at a time with per-step confirmation."""
    import subprocess
    import time as _time

    from shift_cli.executor import is_dangerous

    commands = writer_json.get("final_commands", [])
    results = []
    current_cwd = None
    cwd_stack: list[str] = []

    _blank()
    _rule("Step-by-step Execution")
    _blank()

    for item in commands:
        cmd = item.get("command", "")
        risk = item.get("risk", "safe")
        explain = item.get("explanation", "")
        step = item.get("step_number", 0)

        risk_col = _risk_color(risk)
        _p(
            f"[{C_LABEL}]Step {step}:[/]  [{C_LABEL}]{cmd}[/]  "
            f"[{risk_col}]({risk})[/]"
        )
        _dim(f"  {explain}")

        if is_dangerous(cmd) or risk == "dangerous":
            _err("  BLOCKED — dangerous command.")
            results.append({
                "step_number": step, "command": cmd, "success": False,
                "output": "", "error": "Blocked", "time": 0, "risk": risk,
                "blocked": True,
            })
            continue

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

        go = _ask("  Run this?  [y/N/skip]  >")
        if go.lower() in ("y", "yes"):
            start = _time.time()

            # Determine shell
            use_shell = True
            shell_args = cmd
            if cfg.shell == "powershell":
                use_shell = False
                shell_args = ["powershell.exe", "-Command", cmd]
            elif platform.system().lower() != "windows":
                use_shell = False
                shell_args = ["/bin/bash", "-c", cmd]

            try:
                result = subprocess.run(
                    shell_args, shell=use_shell, cwd=current_cwd,
                    capture_output=True, text=True, timeout=60,
                )
                taken = round(_time.time() - start, 2)
                success = result.returncode == 0
                if success:
                    current_cwd = proposed_cwd
                    cwd_stack = proposed_stack
                    _ok(f"  Done in {taken}s")
                    if result.stdout.strip():
                        _dim(f"  Output: {result.stdout.strip()[:200]}")
                else:
                    _err(f"  Failed: {result.stderr.strip()[:200]}")
                results.append({
                    "step_number": step, "command": cmd, "success": success,
                    "output": result.stdout.strip(), "error": result.stderr.strip(),
                    "time": taken, "risk": risk, "blocked": False,
                })
            except subprocess.TimeoutExpired:
                _err("  Timed out after 60s")
                results.append({
                    "step_number": step, "command": cmd, "success": False,
                    "output": "", "error": "Timeout", "time": 60,
                    "risk": risk, "blocked": False,
                })
            except Exception as exc:
                _err(f"  Error: {exc}")
                results.append({
                    "step_number": step, "command": cmd, "success": False,
                    "output": "", "error": str(exc), "time": 0,
                    "risk": risk, "blocked": False,
                })
        else:
            _dim("  Skipped.")
            results.append({
                "step_number": step, "command": cmd, "success": False,
                "output": "", "error": "Skipped by user", "time": 0,
                "risk": risk, "blocked": False,
            })

    _blank()
    _display_results(results)
    _save_results(task, writer_json, results, memory, cfg)


# ── Display results ───────────────────────────────────────────────────────────

def _display_results(results: list[dict]) -> None:
    """Display execution results in a summary table."""
    if not results:
        return

    _rule("Results")
    _blank()

    succeeded = sum(1 for r in results if r.get("success"))
    failed = sum(1 for r in results if not r.get("success") and not r.get("blocked"))
    blocked = sum(1 for r in results if r.get("blocked"))
    total_time = sum(r.get("time", 0) for r in results)

    _p(
        f"[{C_OK}]{succeeded} succeeded[/]   "
        f"[{C_ERR}]{failed} failed[/]   "
        f"[{C_WARN}]{blocked} blocked[/]   "
        f"[{C_DIM}]Total time: {total_time:.1f}s[/]"
    )
    _blank()

    for r in results:
        step = r.get("step_number", "?")
        cmd = r.get("command", "")
        if r.get("blocked"):
            _p(f"[{C_DIM}]{step}.[/]  [{C_DANGER}]BLOCKED[/]  {cmd[:60]}")
        elif r.get("success"):
            _p(f"[{C_DIM}]{step}.[/]  [{C_OK}]OK[/]      {cmd[:60]}  [{C_DIM}]{r.get('time', 0)}s[/]")
        else:
            err = r.get("error", "")[:60]
            _p(f"[{C_DIM}]{step}.[/]  [{C_ERR}]FAIL[/]    {cmd[:60]}")
            if err:
                _dim(f"          {err}")
    _blank()


# ── Save results to memory ────────────────────────────────────────────────────

def _save_results(
    task: str, writer_json: dict, results: list[dict],
    memory: MemoryStore, cfg: Config,
) -> None:
    """Persist task and command results to history."""
    succeeded = sum(1 for r in results if r.get("success"))
    failed = len(results) - succeeded

    task_id = memory.save_task(
        task=task,
        summary=writer_json.get("summary", ""),
        os_used=cfg.os_name,
        total_cmds=len(results),
        succeeded=succeeded,
        failed=failed,
    )

    for r in results:
        memory.save_command(
            task_id=task_id,
            step_number=r.get("step_number", 0),
            command=r.get("command", ""),
            explanation="",
            risk=r.get("risk", "safe"),
            success=r.get("success", False),
            output=r.get("output", "")[:500],
            error=r.get("error", "")[:500],
            time_secs=r.get("time", 0),
        )


# ── Execute a task ────────────────────────────────────────────────────────────

async def execute_task(
    task: str,
    memory: MemoryStore,
    cfg: Config,
    skip_hitl: bool = False,
) -> None:
    """Full task execution flow: HITL → Pipeline → Display → Execute."""

    memory_ctx = memory.build_context_string() if not memory.is_first_run() else ""
    clarifications = ""

    # Human-in-the-loop
    if not skip_hitl:
        try:
            clarifications = await _run_hitl(task, memory, cfg)
        except (KeyboardInterrupt, EOFError):
            _blank()
            _dim("Clarifications skipped.")
    else:
        _blank()

    # Run the pipeline
    _rule("Running Agent Pipeline")
    _blank()
    _dim("Planner → Researcher → Writer")
    _blank()

    from shift_cli.agents.pipeline import ShiftCLIPipeline

    pipeline = ShiftCLIPipeline(cfg)

    with console.status(
        f"  [{C_DIM}]Agent pipeline running...[/]",
        spinner="line", spinner_style=C_DIM,
    ):
        result = await pipeline.execute(
            task=task,
            os_context=cfg.os_name,
            clarifications=clarifications,
            memory_context=memory_ctx,
            cwd_context=str(Path.cwd()),
        )

    elapsed = result.get("elapsed", 0)
    _dim(f"Pipeline completed in {elapsed:.1f}s")

    if not result.get("success"):
        _err("The agent pipeline did not return a valid execution plan.")
        raw = result.get("raw_output", "")
        error = result.get("error", "")
        if error:
            _err(f"Error: {error}")
        if raw:
            _blank()
            _dim("Raw output from the pipeline:")
            console.print(Panel(
                raw[:2000],
                border_style=C_BORDER,
                padding=(0, 2),
            ))
        return

    writer_json = result["writer_json"]

    # Display the plan
    _display_plan(writer_json)

    # Execute with confirmation
    await _execute_with_confirmation(writer_json, memory, cfg, task)


# ── History command ───────────────────────────────────────────────────────────

def cmd_history(memory: MemoryStore) -> None:
    """Display recent task history."""
    _blank()
    _rule("Task History")
    _blank()

    recent = memory.get_recent_tasks(10)
    if not recent:
        _dim("No tasks in history yet.")
        _blank()
        return

    table = Table(box=box.ROUNDED, border_style=C_BORDER)
    table.add_column("#", style=C_DIM, width=4)
    table.add_column("Task", style=C_LABEL, min_width=30)
    table.add_column("OS", style=C_DIM, width=10)
    table.add_column("Result", width=12)
    table.add_column("Date", style=C_DIM, width=12)

    for t in recent:
        s = t["succeeded"]
        f = t["failed"]
        result_str = f"[{C_OK}]{s}✓[/] [{C_ERR}]{f}✗[/]"
        table.add_row(
            str(t["id"]),
            t["task"][:50],
            t.get("os_used", "")[:10],
            result_str,
            t["created_at"][:10],
        )

    console.print(table)
    _blank()


# ── Help ──────────────────────────────────────────────────────────────────────

def _print_help() -> None:
    _blank()
    _p(f"[{C_LABEL}]Commands:[/]")
    _dim("  Any text          Describe a task to automate")
    _dim("  setup             Reconfigure your Azure AI Foundry endpoint")
    _dim("  history           View past tasks and their results")
    _dim("  clear history     Wipe all stored history")
    _dim("  help              Show this help message")
    _dim("  exit / quit       End the session")
    _blank()


# ── Interactive REPL ──────────────────────────────────────────────────────────

async def interactive_mode(
    cfg: Config,
    memory: MemoryStore,
    skip_hitl: bool = False,
) -> None:
    """Main interactive loop."""
    _banner()

    _greet(memory, cfg)

    _p(
        f"[{C_DIM}]Describe a terminal task in plain English.  "
        f"Type 'help' for commands, 'exit' to leave.[/]"
    )
    _blank()

    while True:
        try:
            task = _ask(">")
        except (KeyboardInterrupt, EOFError):
            _blank()
            _dim("Session closed.")
            _blank()
            break

        if not task:
            continue

        low = task.lower().strip()

        if low in ("exit", "quit", "q"):
            _blank()
            _dim("Session closed.")
            _blank()
            break
        elif low == "help":
            _print_help()
        elif low == "history":
            cmd_history(memory)
        elif low == "setup":
            await run_setup(cfg, force=True)
        elif low == "clear history":
            _blank()
            confirm = _ask("Type 'confirm' to erase all history  >")
            if confirm.lower() == "confirm":
                memory.db_path.unlink(missing_ok=True)
                memory.initialize()
                _ok("History cleared.")
            else:
                _dim("Cancelled.")
            _blank()
        else:
            try:
                await execute_task(task, memory, cfg, skip_hitl=skip_hitl)
            except KeyboardInterrupt:
                _blank()
                _warn("Task interrupted.")
                _blank()
            except Exception as exc:
                _err(f"Pipeline error: {exc}")
                _blank()

    memory.close()


# ── Argument parsing ──────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="shift_cli",
        description="Shift_CLI — AI-Powered Terminal Automation Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  shift_cli                                    interactive session\n"
            "  shift_cli -t 'set up a Python project'       single task\n"
            "  shift_cli setup                              configure endpoint\n"
            "  shift_cli history                            view past tasks\n"
            "  shift_cli --no-hitl -t 'your task'           skip questions\n"
        ),
    )
    p.add_argument("command", nargs="?", help="Command: setup, history")
    p.add_argument("-t", "--task", default=None, help="Run a single task non-interactively")
    p.add_argument("--no-hitl", action="store_true", help="Skip clarifying questions")
    p.add_argument("--history-path", default=None, help="Custom path for history database")
    return p.parse_args()


# ── Entry point ───────────────────────────────────────────────────────────────

async def async_main() -> None:
    args = parse_args()
    cfg = Config()
    memory = MemoryStore(db_path=args.history_path)
    memory.initialize()

    # ── Subcommands ───────────────────────────────────────────────────────────
    if args.command == "setup":
        _banner()
        await run_setup(cfg, force=True)
        return

    if args.command == "history":
        _banner()
        cmd_history(memory)
        return

    # ── First-run: must configure endpoint ────────────────────────────────────
    if not cfg.is_configured():
        _banner()
        _p(f"[{C_LABEL}]Shift_CLI is not configured yet.[/]")
        _blank()
        await run_setup(cfg)
        if not cfg.is_configured():
            _err("Setup incomplete. Run 'shift_cli setup' to configure.")
            return

    # ── Single-task mode ──────────────────────────────────────────────────────
    if args.task:
        _banner()
        _greet(memory, cfg)
        await execute_task(
            args.task, memory, cfg,
            skip_hitl=args.no_hitl,
        )
        memory.close()
        return

    # ── Interactive mode ──────────────────────────────────────────────────────
    await interactive_mode(cfg, memory, skip_hitl=args.no_hitl)


def main() -> None:
    """CLI entry point called by `shift_cli` command."""
    asyncio.run(async_main())


if __name__ == "__main__":
    main()
