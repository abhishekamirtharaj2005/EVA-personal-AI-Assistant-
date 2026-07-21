"""
EVA Flight Finder — Find flights via Google Flights + Playwright + Gemini extraction.
"""

import logging
from datetime import datetime

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.flight_finder")


def _build_flights_url(origin: str, destination: str,
                       depart_date: str, return_date: str = "") -> str:
    """Build a Google Flights search URL."""
    base = "https://www.google.com/travel/flights"
    params = f"?q=flights+from+{origin}+to+{destination}"
    if depart_date:
        params += f"+on+{depart_date}"
    if return_date:
        params += f"+returning+{return_date}"
    return base + params


@register_tool(
    name="search_flights",
    description="Search for flights between cities. Opens Google Flights, "
                "captures the page, and extracts pricing/schedule data.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "origin": {
                "type": "STRING",
                "description": "Departure city or airport code (e.g., 'London', 'LHR')",
            },
            "destination": {
                "type": "STRING",
                "description": "Arrival city or airport code",
            },
            "depart_date": {
                "type": "STRING",
                "description": "Departure date (YYYY-MM-DD or natural language like 'next Friday')",
            },
            "return_date": {
                "type": "STRING",
                "description": "Return date (optional, for round trip)",
            },
        },
        "required": ["origin", "destination"],
    },
    category="utility",
)
async def search_flights(origin: str, destination: str,
                         depart_date: str = "", return_date: str = "") -> str:
    """Search for flights using Google Flights."""
    url = _build_flights_url(origin, destination, depart_date, return_date)

    try:
        from actions.browser_control import open_browser, get_page_content

        # Open Google Flights
        await open_browser(url, wait_for_load=True)

        import asyncio
        await asyncio.sleep(3)  # Wait for flight results to load

        # Get page content
        content = await get_page_content()

        if not content or len(content) < 100:
            return (f"Opened Google Flights for {origin} → {destination}. "
                    f"Please check the browser for results.")

        # Use Gemini to extract structured flight data
        import google.generativeai as genai
        from memory.config_manager import config

        genai.configure(api_key=config.get("api_key"))
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = (
            f"Extract flight information from this Google Flights page content. "
            f"Route: {origin} → {destination}. "
            f"List the top 5 flight options with: airline, departure time, "
            f"arrival time, duration, stops, and price. Format as a clean list.\n\n"
            f"Page content:\n{content[:6000]}"
        )

        response = model.generate_content(prompt)
        if response and response.text:
            return response.text

        return f"Opened Google Flights for {origin} → {destination}. Check browser for details."

    except Exception as e:
        logger.error(f"Flight search failed: {e}")
        # Fallback: open URL in system browser
        import webbrowser
        webbrowser.open(url)
        return f"Opened Google Flights in browser for {origin} → {destination}."
