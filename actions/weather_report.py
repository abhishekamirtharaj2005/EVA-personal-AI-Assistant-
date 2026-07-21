"""
EVA Weather Report — Fetches weather conditions using web search.
Pulls saved city from memory.
"""

import logging

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.weather_report")


@register_tool(
    name="get_weather",
    description="Get current weather conditions for a city. "
                "If no city specified, uses the saved city from memory.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "city": {
                "type": "STRING",
                "description": "City name (e.g., 'London', 'New York'). "
                               "Optional if city is saved in memory.",
            },
        },
        "required": [],
    },
    category="utility",
)
def get_weather(city: str = "") -> str:
    """Fetch current weather for a city."""
    from memory.config_manager import config
    from memory.memory_manager import memory

    if not city:
        city = config.get("city", "")
    if not city:
        # Check memory
        recall = memory.recall(key="city", category="preferences")
        if recall and recall != "No matching memories found.":
            city = recall.split(":")[-1].strip()

    if not city:
        return "I don't know your city. Please tell me which city's weather you'd like."

    # Save city for future use
    memory.remember("city", city, "preferences")

    # Use web search for weather
    try:
        from actions.web_search import search_web
        result = search_web(query=f"current weather in {city}", mode="search")
        return f"Weather for {city}:\n{result}"
    except Exception as e:
        logger.error(f"Weather fetch failed: {e}")
        return f"Couldn't fetch weather for {city}: {e}"
