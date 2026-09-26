"""
EVA Location Services — Location-aware features using IP geolocation
and optional phone GPS. Nearby places, traffic, weather by location.
"""

import json
import logging
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.location")


def _get_ip_location() -> Optional[dict]:
    """Get approximate location from IP address."""
    try:
        import requests
        resp = requests.get("https://ipinfo.io/json", timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            loc = data.get("loc", "0,0").split(",")
            return {
                "city": data.get("city", "Unknown"),
                "region": data.get("region", ""),
                "country": data.get("country", ""),
                "lat": float(loc[0]),
                "lon": float(loc[1]),
                "ip": data.get("ip", ""),
                "org": data.get("org", ""),
                "timezone": data.get("timezone", ""),
            }
    except Exception as e:
        logger.error(f"IP location failed: {e}")
    return None


def _search_nearby(lat: float, lon: float, query: str) -> str:
    """Search for nearby places using web search as fallback."""
    try:
        from actions.web_search import search_web
        return search_web(
            query=f"{query} near me in {lat},{lon}",
            mode="search"
        )
    except Exception as e:
        return f"Search failed: {e}"


@register_tool(
    name="location_service",
    description="Location-aware features — find your location, nearby places, "
                "traffic info, distance calculations, and local recommendations. "
                "Uses IP-based geolocation (no GPS needed).",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: where_am_i | nearby | traffic | distance | local_info",
            },
            "query": {
                "type": "STRING",
                "description": "Search query for nearby/local_info. "
                               "E.g., 'coffee shops', 'gas stations', 'hospitals'",
            },
            "destination": {
                "type": "STRING",
                "description": "Destination for traffic/distance. E.g., 'office', 'airport'",
            },
        },
        "required": ["action"],
    },
    category="utility",
)
def location_service(action: str, query: str = "", destination: str = "") -> str:
    """Location-based services."""
    action = action.lower().strip()

    loc = _get_ip_location()
    if not loc:
        return "Couldn't determine your location. Check your internet connection."

    # ── Where am I ───────────────────────────────────────────
    if action == "where_am_i":
        return (
            f"📍 Your location (approximate via IP):\n"
            f"   City: {loc['city']}, {loc['region']}\n"
            f"   Country: {loc['country']}\n"
            f"   Coordinates: {loc['lat']}, {loc['lon']}\n"
            f"   Timezone: {loc['timezone']}\n"
            f"   ISP: {loc['org']}"
        )

    # ── Nearby places ────────────────────────────────────────
    elif action == "nearby":
        if not query:
            return "What are you looking for nearby? E.g., 'coffee shops', 'ATMs', 'pharmacies'"

        try:
            from actions.web_search import search_web
            result = search_web(
                query=f"best {query} near {loc['city']}, {loc['region']}",
                mode="search"
            )
            return f"📍 {query.title()} near {loc['city']}:\n{result}"
        except Exception as e:
            return f"Search failed: {e}"

    # ── Traffic ──────────────────────────────────────────────
    elif action == "traffic":
        if not destination:
            return "Where are you going? Give me a destination."

        try:
            from actions.web_search import search_web
            result = search_web(
                query=f"traffic from {loc['city']} to {destination} right now",
                mode="search"
            )
            return f"🚗 Traffic to {destination} from {loc['city']}:\n{result}"
        except Exception as e:
            return f"Traffic check failed: {e}"

    # ── Distance ─────────────────────────────────────────────
    elif action == "distance":
        if not destination:
            return "Distance to where?"

        try:
            from actions.web_search import search_web
            result = search_web(
                query=f"distance from {loc['city']} to {destination}",
                mode="search"
            )
            return f"📏 Distance from {loc['city']} to {destination}:\n{result}"
        except Exception as e:
            return f"Distance check failed: {e}"

    # ── Local info ───────────────────────────────────────────
    elif action == "local_info":
        query = query or "things to do"
        try:
            from actions.web_search import search_web
            result = search_web(
                query=f"{query} in {loc['city']}, {loc['region']}",
                mode="search"
            )
            return f"📍 {query.title()} in {loc['city']}:\n{result}"
        except Exception as e:
            return f"Local info failed: {e}"

    return f"Unknown location action '{action}'. Use: where_am_i, nearby, traffic, distance, local_info."
