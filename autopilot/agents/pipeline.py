"""
autopilot/agents/pipeline.py — 3-stage automation pipeline
===========================================================

Uses Azure AI Foundry's conversation API to run the multi-agent
workflow (Planner → Researcher → Writer).

The Foundry workflow handles the agent orchestration internally.
This module sends the user's task and collects the final JSON
execution plan from the Writer Agent.
"""

from __future__ import annotations

import asyncio
import json
import re
import time
from typing import Any, Callable, Awaitable

from autopilot.config import Config


class AutoPilotPipeline:
    """
    Runs the AutoPilot multi-agent workflow via Azure AI Foundry.

    The Foundry workflow contains 3 agents (Planner, Researcher, Writer)
    that chain together to convert a natural language task into an
    executable command plan.
    """

    def __init__(self, config: Config) -> None:
        self.config = config
        self._client = None
        self._openai = None

    def _get_clients(self) -> tuple:
        """Initialize Azure AI Project client and OpenAI client."""
        if self._client is None:
            from azure.identity import DefaultAzureCredential
            from azure.ai.projects import AIProjectClient

            self._client = AIProjectClient(
                endpoint=self.config.endpoint,
                credential=DefaultAzureCredential(),
            )
            self._openai = self._client.get_openai_client()
        return self._client, self._openai

    def _run_workflow(self, task_input: str) -> str:
        """Run the Foundry workflow and collect all response text."""
        _, openai_client = self._get_clients()

        conversation = openai_client.conversations.create()
        collected_text: list[str] = []
        actor_outputs: dict[str, list[str]] = {}
        current_actor = "unknown"

        try:
            stream = openai_client.responses.create(
                conversation=conversation.id,
                extra_body={
                    "agent_reference": {
                        "name": self.config.workflow_name,
                        "type": "agent_reference",
                    }
                },
                input=task_input,
                stream=True,
                metadata={"x-ms-debug-mode-enabled": "1"},
            )

            for event in stream:
                if event.type == "response.output_text.done":
                    collected_text.append(event.text)
                    if current_actor not in actor_outputs:
                        actor_outputs[current_actor] = []
                    actor_outputs[current_actor].append(event.text)
                elif (
                    event.type == "response.output_item.added"
                    and event.item.type == "workflow_action"
                ):
                    current_actor = event.item.action_id
                elif event.type == "response.output_text.delta":
                    pass  # streaming delta, ignore for now

        finally:
            openai_client.conversations.delete(conversation_id=conversation.id)

        return "\n".join(collected_text)

    async def execute(
        self,
        task: str,
        os_context: str = "",
        clarifications: str = "",
        memory_context: str = "",
        cwd_context: str = "",
        progress_cb: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict[str, Any]:
        """
        Run the full pipeline.

        Returns a dict with:
          writer_json   — parsed JSON from the Writer Agent
          raw_output    — full raw text from the workflow
          elapsed       — total seconds
          success       — whether we got valid JSON
        """
        t0 = time.time()

        # Build the task input with context
        parts: list[str] = []
        if os_context:
            parts.append(f"Target OS: {os_context}")
        if cwd_context:
            parts.append(f"Current working directory: {cwd_context}")
        if memory_context:
            parts.append(memory_context)
        if clarifications:
            parts.append(clarifications)
        parts.append(f"Task: {task}")
        task_input = "\n\n".join(parts)

        if progress_cb:
            await progress_cb("pipeline", "running")

        # Run in executor to avoid blocking
        loop = asyncio.get_running_loop()
        try:
            raw_output = await loop.run_in_executor(None, self._run_workflow, task_input)
        except Exception as exc:
            if progress_cb:
                await progress_cb("pipeline", "failed")
            return {
                "writer_json": {},
                "raw_output": str(exc),
                "elapsed": time.time() - t0,
                "success": False,
                "error": str(exc),
            }

        # Try to extract JSON from the raw output
        writer_json = _extract_json(raw_output)

        if progress_cb:
            await progress_cb("pipeline", "done")

        elapsed = time.time() - t0
        return {
            "writer_json": writer_json,
            "raw_output": raw_output,
            "elapsed": elapsed,
            "success": bool(writer_json and writer_json.get("final_commands")),
        }


def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract the Writer Agent's JSON from the raw workflow output.

    Handles:
    - Multiple JSON objects (picks the one with 'final_commands')
    - Markdown code fences
    - Think blocks
    - Truncated JSON
    """
    import json_repair

    # Strip think blocks
    text_clean = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    if "<think>" in text_clean:
        text_clean = text_clean[:text_clean.find("<think>")]

    # Strip markdown fences
    text_clean = re.sub(r"^```(?:json)?\s*", "", text_clean, flags=re.MULTILINE)
    text_clean = re.sub(r"\s*```$", "", text_clean, flags=re.MULTILINE)

    # Try to find all JSON objects
    json_candidates: list[dict] = []
    brace_depth = 0
    start_idx = -1

    for i, ch in enumerate(text_clean):
        if ch == "{":
            if brace_depth == 0:
                start_idx = i
            brace_depth += 1
        elif ch == "}":
            brace_depth -= 1
            if brace_depth == 0 and start_idx >= 0:
                candidate = text_clean[start_idx:i + 1]
                try:
                    parsed = json.loads(candidate)
                    json_candidates.append(parsed)
                except json.JSONDecodeError:
                    try:
                        parsed = json_repair.repair_json(candidate, return_objects=True)
                        if isinstance(parsed, dict):
                            json_candidates.append(parsed)
                    except Exception:
                        pass
                start_idx = -1

    # Find the one with 'final_commands' (Writer Agent output)
    for candidate in json_candidates:
        if isinstance(candidate, dict) and "final_commands" in candidate:
            return candidate

    # If no Writer output found, return the last JSON object
    if json_candidates:
        return json_candidates[-1]

    # Last resort: try to parse the entire text
    try:
        return json.loads(text_clean.strip())
    except Exception:
        pass

    try:
        result = json_repair.repair_json(text_clean.strip(), return_objects=True)
        if isinstance(result, dict):
            return result
    except Exception:
        pass

    return {}
