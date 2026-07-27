"""
EVA Tool Dispatcher
Data-driven {name: callable} dispatch table with decorator-based registration.
Each tool module self-registers on import. Dispatch runs blocking I/O
off the event loop via thread pool.
"""

import asyncio
import functools
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

logger = logging.getLogger("eva.tools")

# Thread pool for blocking tool execution
_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="eva-tool")


@dataclass
class ToolEntry:
    """A registered tool with its callable and Gemini function declaration."""
    name: str
    func: Callable[..., Any]
    description: str
    parameters: dict[str, Any]
    # Optional metadata
    category: str = "general"
    cooldown_seconds: float = 0.0
    _last_called: float = field(default=0.0, repr=False)


# ── Global registry ─────────────────────────────────────────────

_REGISTRY: dict[str, ToolEntry] = {}


def register_tool(
    name: str,
    description: str,
    parameters: dict[str, Any],
    category: str = "general",
    cooldown_seconds: float = 0.0,
) -> Callable:
    """
    Decorator to register a function as a tool.

    Usage:
        @register_tool(
            name="search_web",
            description="Search the web for current information",
            parameters={
                "type": "OBJECT",
                "properties": {
                    "query": {"type": "STRING", "description": "Search query"},
                    "mode": {"type": "STRING", "description": "Search mode",
                             "enum": ["news", "research", "price", "compare", "search"]},
                },
                "required": ["query"],
            },
        )
        def search_web(query: str, mode: str = "search") -> str:
            ...
    """
    def decorator(func: Callable) -> Callable:
        entry = ToolEntry(
            name=name,
            func=func,
            description=description,
            parameters=parameters,
            category=category,
            cooldown_seconds=cooldown_seconds,
        )
        _REGISTRY[name] = entry
        logger.debug(f"Registered tool: {name}")

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)

        wrapper._tool_entry = entry  # type: ignore
        return wrapper

    return decorator


# ── Dispatch ────────────────────────────────────────────────────

async def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """
    Dispatch a tool call by name. Runs the callable in a thread pool
    to keep blocking I/O off the event loop. Returns a result dict
    suitable for wrapping as a FunctionResponse.
    """
    entry = _REGISTRY.get(name)
    if entry is None:
        logger.error(f"Unknown tool: {name}")
        return {"error": f"Unknown tool: {name}"}

    # Cooldown check
    import time
    now = time.time()
    if entry.cooldown_seconds > 0 and (now - entry._last_called) < entry.cooldown_seconds:
        logger.warning(f"Tool {name} on cooldown ({entry.cooldown_seconds}s)")
        return {"result": f"Tool {name} was called too recently. Please wait."}

    entry._last_called = now
    logger.info(f"Dispatching tool: {name}({args})")

    try:
        loop = asyncio.get_event_loop()
        # If the function is a coroutine, await it directly
        if asyncio.iscoroutinefunction(entry.func):
            result = await entry.func(**args)
        else:
            # Run blocking function in thread pool
            result = await loop.run_in_executor(
                _executor,
                functools.partial(entry.func, **args)
            )

        # Normalize result to string
        if isinstance(result, dict):
            return {"result": result}
        return {"result": str(result) if result is not None else "Done."}

    except Exception as e:
        logger.exception(f"Tool {name} failed: {e}")
        return {"error": f"Tool {name} failed: {str(e)}"}


# ── Declaration generation ──────────────────────────────────────

def get_all_declarations() -> list[dict]:
    """
    Return Gemini-compatible function declarations for all registered tools.
    Format suitable for the LiveConnectConfig tools parameter.
    """
    declarations = []
    for entry in _REGISTRY.values():
        decl = {
            "name": entry.name,
            "description": entry.description,
            "parameters": entry.parameters,
        }
        declarations.append(decl)
    return declarations


def get_tool_names() -> list[str]:
    """Return a sorted list of all registered tool names."""
    return sorted(_REGISTRY.keys())


def get_tool_count() -> int:
    """Return the number of registered tools."""
    return len(_REGISTRY)


# ── Import all action modules to trigger registration ───────────

def load_all_tools() -> None:
    """
    Import all action modules so their @register_tool decorators fire.
    Called once at startup.
    """
    # Each import triggers the @register_tool decorators in that module
    import actions.web_search
    import actions.screen_processor
    import actions.reminder
    import actions.system_monitor
    import actions.computer_settings
    import actions.computer_control
    import actions.open_app
    import actions.browser_control
    import actions.file_controller
    import actions.file_processor
    import actions.send_message
    import actions.weather_report
    import actions.flight_finder
    import actions.youtube_video
    import actions.game_updater
    import actions.code_helper
    import actions.dev_agent
    import actions.desktop
    import actions.proactive
    import actions.topic_monitor

    logger.info(f"Loaded {get_tool_count()} tools: {get_tool_names()}")
