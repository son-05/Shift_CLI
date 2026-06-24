"""
shift_cli/hitl/questioner.py — Clarifying question generator
=============================================================

Generates targeted clarifying questions before executing a task.
Uses the Foundry endpoint to ask the LLM for context-specific questions.
"""

from __future__ import annotations

import asyncio
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from shift_cli.config import Config


async def generate_questions(
    task: str,
    os_context: str = "",
    memory_context: str = "",
    max_questions: int = 3,
    cwd_context: str = "",
    cfg: Config | None = None,
) -> list[str]:
    """
    Generate targeted clarifying questions for a terminal task.

    Uses the Foundry endpoint. Falls back to defaults if the call fails.
    """
    if not cfg:
        from shift_cli.config import Config
        cfg = Config()

    try:
        return await _llm_questions(task, os_context, memory_context, max_questions, cwd_context, cfg)
    except Exception:
        return _default_questions(task, os_context)[:max_questions]


async def _llm_questions(
    task: str,
    os_context: str,
    memory_context: str,
    max_q: int,
    cwd_context: str,
    cfg: Config,
) -> list[str]:
    from shift_cli.agents.prompts import HITL_SYSTEM, format_prompt

    system = format_prompt(
        HITL_SYSTEM,
        max_questions=str(max_q),
        os_context=os_context or cfg.os_name,
    )

    user_parts = [f"Terminal task: {task}"]
    if os_context:
        user_parts.append(f"Operating system: {os_context}")
    if cwd_context:
        user_parts.append(f"Current working directory: {cwd_context}")
    if memory_context:
        user_parts.append(f"\nContext from history:\n{memory_context}")
    user_parts.append(f"\nGenerate {max_q} clarifying questions.")
    user_msg = "\n".join(user_parts)

    loop = asyncio.get_running_loop()

    def _call() -> str:
        from azure.ai.projects import AIProjectClient
        from azure.identity import DefaultAzureCredential

        client = AIProjectClient(
            endpoint=cfg.endpoint,
            credential=DefaultAzureCredential(),
        )
        openai_client = client.get_openai_client()

        # Use the underlying model directly for quick Q&A
        resp = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=400,
            temperature=0.4,
        )
        return resp.choices[0].message.content or ""

    raw = await loop.run_in_executor(None, _call)
    return _parse_questions(raw)[:max_q]


def _parse_questions(raw: str) -> list[str]:
    """Extract numbered questions from raw LLM output."""
    questions = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        cleaned = re.sub(r"^[\d]+[.):\s]+", "", line).strip()
        if len(cleaned) > 15:
            questions.append(cleaned)
    return questions


def _default_questions(task: str, os_context: str = "") -> list[str]:
    """Fallback questions when LLM is unavailable."""
    return [
        "What name would you like for the project or directory? "
        "(or should I use a default name?)",
        "Do you have any specific tool versions or preferences? "
        "(e.g. Python 3.12, Node 20, specific frameworks)",
        "Should I include any extra setup like git init, linting config, "
        "or CI/CD templates?",
    ]
