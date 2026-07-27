"""
EVA Web Search — Multi-mode web search tool.
For news mode: races DDG News vs Gemini grounded search in parallel.
First valid result wins; the loser is discarded.
"""

import logging
import threading
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.web_search")


def _duckduckgo_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo text search."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [
                {"title": r.get("title", ""), "body": r.get("body", ""),
                 "url": r.get("href", "")}
                for r in results
            ]
    except Exception as e:
        logger.warning(f"DuckDuckGo search failed: {e}")
        return []


def _duckduckgo_news(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo news search."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.news(query, max_results=max_results))
            return [
                {"title": r.get("title", ""), "body": r.get("body", ""),
                 "url": r.get("url", ""), "date": r.get("date", "")}
                for r in results
            ]
    except Exception as e:
        logger.warning(f"DuckDuckGo news search failed: {e}")
        return []


def _gemini_grounded_search(query: str) -> Optional[str]:
    """Use Gemini with grounding for high-quality search results."""
    try:
        import google.generativeai as genai
        from memory.config_manager import config
        api_key = config.get("api_key")
        if not api_key:
            return None

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            f"Search the web and provide current information about: {query}",
            tools="google_search_retrieval",
        )
        if response and response.text:
            return response.text
    except Exception as e:
        logger.warning(f"Gemini grounded search failed: {e}")
    return None


def _format_results(results: list[dict], mode: str) -> str:
    """Format search results into a readable string."""
    if not results:
        return "No results found."

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "Untitled")
        body = r.get("body", r.get("snippet", ""))
        url = r.get("url", "")
        date = r.get("date", "")

        line = f"{i}. **{title}**"
        if date:
            line += f" ({date})"
        if body:
            line += f"\n   {body[:200]}"
        if url:
            line += f"\n   Source: {url}"
        lines.append(line)

    return "\n\n".join(lines)


# ── Parallel News Race ──────────────────────────────────────────

_MIN_VALID_LENGTH = 50  # Minimum chars for a "valid" result


def _race_news_search(query: str) -> str:
    """
    Race DDG News vs Gemini grounded search.
    First valid result wins. Loser is discarded.
    Uses Lock + Event for thread-safe first-write-wins.
    """
    result_slot: list[Optional[str]] = [None]
    result_lock = threading.Lock()
    done_event = threading.Event()
    fail_count = [0]

    def _try_ddg():
        try:
            results = _duckduckgo_news(query, max_results=5)
            if results:
                formatted = _format_results(results, "news")
                if len(formatted) >= _MIN_VALID_LENGTH:
                    with result_lock:
                        if result_slot[0] is None:
                            result_slot[0] = formatted
                            logger.info("News race: DDG won")
                    done_event.set()
                    return
        except Exception as e:
            logger.warning(f"DDG news race failed: {e}")

        with result_lock:
            fail_count[0] += 1
            if fail_count[0] >= 2:
                done_event.set()

    def _try_gemini():
        try:
            adapted = f"latest news {query}"
            result = _gemini_grounded_search(adapted)
            if result and len(result) >= _MIN_VALID_LENGTH:
                with result_lock:
                    if result_slot[0] is None:
                        result_slot[0] = result
                        logger.info("News race: Gemini won")
                done_event.set()
                return
        except Exception as e:
            logger.warning(f"Gemini news race failed: {e}")

        with result_lock:
            fail_count[0] += 1
            if fail_count[0] >= 2:
                done_event.set()

    # Launch both as daemon threads
    t1 = threading.Thread(target=_try_ddg, daemon=True)
    t2 = threading.Thread(target=_try_gemini, daemon=True)
    t1.start()
    t2.start()

    # Wait for first valid result (or timeout)
    done_event.wait(timeout=10.0)

    with result_lock:
        winner = result_slot[0]

    if winner:
        return winner

    return "I couldn't find any news results. Please try rephrasing your query."


# ── Main Tool ───────────────────────────────────────────────────

@register_tool(
    name="search_web",
    description="Search the web for current information. Supports multiple modes: "
                "'news' for latest news, 'research' for in-depth info, 'price' for "
                "product prices, 'compare' for comparisons, 'search' for general queries.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "The search query"
            },
            "mode": {
                "type": "STRING",
                "description": "Search mode: news, research, price, compare, or search",
                "enum": ["news", "research", "price", "compare", "search"]
            },
        },
        "required": ["query"],
    },
    category="web",
    cooldown_seconds=3.0,
)
def search_web(query: str, mode: str = "search") -> str:
    """
    Multi-mode web search.
    - News mode: races DDG News vs Gemini grounded (first wins).
    - Other modes: Gemini primary, DDG fallback.
    """
    logger.info(f"Web search: mode={mode}, query='{query}'")

    # ── NEWS MODE: parallel race ────────────────────────────
    if mode == "news":
        return _race_news_search(query)

    # ── OTHER MODES: Gemini primary + DDG fallback ──────────
    if mode == "price":
        adapted_query = f"current price {query}"
    elif mode == "compare":
        adapted_query = f"comparison {query}"
    elif mode == "research":
        adapted_query = f"{query} detailed analysis"
    else:
        adapted_query = query

    # Try Gemini grounded search first
    gemini_result = _gemini_grounded_search(adapted_query)
    if gemini_result and len(gemini_result) >= _MIN_VALID_LENGTH:
        # Also fetch DDG for additional sources
        ddg_results = _duckduckgo_search(adapted_query, 3)
        if ddg_results:
            gemini_result += "\n\n---\nAdditional sources:\n"
            gemini_result += _format_results(ddg_results, mode)
        return gemini_result

    # Fallback to DuckDuckGo
    ddg_results = _duckduckgo_search(adapted_query, 5)
    if ddg_results:
        return _format_results(ddg_results, mode)

    # Last resort: ask Ollama from its general knowledge
    try:
        from core.ollama_client import ollama
        if ollama.is_available():
            result = ollama.generate(
                f"Answer this question based on your knowledge: {adapted_query}"
            )
            if result and len(result) >= _MIN_VALID_LENGTH:
                return (
                    f"*[Answered from local LLM — no live web data]*\n\n"
                    f"{result}"
                )
    except Exception:
        pass

    return "I couldn't find any results for that query. Please try rephrasing."


def fetch_news(topic: str = "top news today") -> str:
    """Convenience function for pre-fetching news (startup briefing)."""
    return search_web(query=topic, mode="news")
