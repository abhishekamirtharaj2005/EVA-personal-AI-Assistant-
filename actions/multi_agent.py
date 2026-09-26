"""
EVA Multi-Agent Workflows — Spawn parallel sub-agents for complex tasks.
Uses Gemini text API (not Live) to run research, coding, and verification
agents concurrently, then consolidates results.
"""

import asyncio
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.multi_agent")

_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="eva-agent")


def _call_gemini(prompt: str, system: str = "") -> str:
    """Call Gemini text API for a sub-agent task."""
    try:
        from google import genai
        from memory.config_manager import config

        api_key = config.get("gemini_api_key", "") or config.get("api_key", "")
        if not api_key:
            return "Error: No API key configured."

        client = genai.Client(api_key=api_key)

        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        response = client.models.generate_content(
            model="gemini-2.0-flash",
            contents=full_prompt,
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"Agent call failed: {e}")
        return f"Error: {e}"


def _run_agent(name: str, task: str, system: str = "") -> dict:
    """Run a single sub-agent and return its result."""
    logger.info(f"Agent '{name}' starting: {task[:80]}...")
    result = _call_gemini(task, system)
    logger.info(f"Agent '{name}' done ({len(result)} chars)")
    return {"agent": name, "result": result}


@register_tool(
    name="multi_agent",
    description="Run complex multi-step tasks using parallel AI agents. "
                "Spawns specialized sub-agents (researcher, coder, reviewer, planner) "
                "that work simultaneously. Use for tasks requiring research + "
                "implementation, comparisons, or multi-phase projects.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "task": {
                "type": "STRING",
                "description": "The complex task to accomplish. Be specific. "
                               "E.g., 'Research the top 5 React chart libraries, "
                               "compare their features, and recommend the best one'",
            },
            "mode": {
                "type": "STRING",
                "description": "Workflow mode: research (gather + analyze), "
                               "build (plan + code + test), compare (multi-option analysis), "
                               "custom (custom agents)",
            },
            "agents": {
                "type": "ARRAY",
                "items": {"type": "STRING"},
                "description": "Custom agent roles for custom mode. "
                               "E.g., ['market_researcher', 'data_analyst', 'writer']",
            },
        },
        "required": ["task"],
    },
    category="advanced",
)
def multi_agent(
    task: str,
    mode: str = "research",
    agents: list[str] = None,
) -> str:
    """Execute multi-agent workflow."""
    mode = mode.lower().strip()

    # ── Define agent configurations ──────────────────────────
    if mode == "research":
        agent_configs = [
            ("Researcher", f"Research the following topic thoroughly. Find facts, data, and key points:\n\n{task}",
             "You are a thorough research analyst. Provide factual, well-sourced information."),
            ("Analyzer", f"Analyze the implications, pros/cons, and key takeaways of:\n\n{task}",
             "You are a critical analyst. Identify patterns, risks, and opportunities."),
            ("Summarizer", f"Create a clear, actionable summary with recommendations for:\n\n{task}",
             "You are a concise summarizer. Distill complex info into clear takeaways."),
        ]

    elif mode == "build":
        agent_configs = [
            ("Planner", f"Create a detailed technical plan for:\n\n{task}\n\nInclude architecture, file structure, and dependencies.",
             "You are a senior software architect."),
            ("Coder", f"Write the core implementation code for:\n\n{task}\n\nProvide complete, working code.",
             "You are an expert software developer. Write clean, production-quality code."),
            ("Reviewer", f"Review and identify bugs, edge cases, and improvements for a project that:\n\n{task}",
             "You are a code reviewer. Focus on correctness, performance, and best practices."),
        ]

    elif mode == "compare":
        agent_configs = [
            ("Option_A", f"Argue FOR the first/primary option in:\n\n{task}\n\nBe thorough and fair.",
             "Present the strongest case with evidence."),
            ("Option_B", f"Argue FOR the alternative/secondary option in:\n\n{task}\n\nBe thorough and fair.",
             "Present the strongest case with evidence."),
            ("Judge", f"Compare both sides objectively and give a final recommendation for:\n\n{task}",
             "You are an impartial evaluator. Weigh evidence and recommend clearly."),
        ]

    elif mode == "custom" and agents:
        agent_configs = [
            (name, f"As a {name}, work on this task:\n\n{task}",
             f"You are a specialized {name}.")
            for name in agents[:5]  # Max 5 custom agents
        ]
    else:
        agent_configs = [
            ("Researcher", f"Research: {task}", "You are a research assistant."),
            ("Analyst", f"Analyze: {task}", "You are an analytical thinker."),
        ]

    # ── Run agents in parallel ───────────────────────────────
    logger.info(f"Multi-agent: {mode} mode, {len(agent_configs)} agents")
    import concurrent.futures

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        futures = {
            pool.submit(_run_agent, name, prompt, system): name
            for name, prompt, system in agent_configs
        }
        for future in concurrent.futures.as_completed(futures, timeout=60):
            try:
                results.append(future.result())
            except Exception as e:
                name = futures[future]
                results.append({"agent": name, "result": f"Error: {e}"})

    # ── Consolidate results ──────────────────────────────────
    lines = [f"🤖 Multi-Agent Report ({mode.upper()} mode)\n{'='*50}\n"]

    for r in results:
        agent_name = r["agent"]
        agent_result = r["result"][:1500]  # Truncate very long results
        lines.append(f"\n📋 Agent: {agent_name}\n{'-'*30}\n{agent_result}\n")

    return "\n".join(lines)
