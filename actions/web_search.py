"""
EVA Web Search — Multi-mode web search tool.
Runs Gemini-grounded search and DuckDuckGo concurrently (primary + fallback).
"""

import logging
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.web_search")
_search_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="search")


def _duckduckgo_search(query: str, max_results: int = 5) -> list[dict]:
    """DuckDuckGo search (fallback)."""
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
    Multi-mode web search. Runs Gemini grounded search and DuckDuckGo
    concurrently, using the best available result.
    """
    logger.info(f"Web search: mode={mode}, query='{query}'")

    # Adapt query for mode
    if mode == "news":
        adapted_query = f"latest news {query}"
    elif mode == "price":
        adapted_query = f"current price {query}"
    elif mode == "compare":
        adapted_query = f"comparison {query}"
    elif mode == "research":
        adapted_query = f"{query} detailed analysis"
    else:
        adapted_query = query

    # Run both search engines concurrently
    gemini_result = None
    ddg_results = []

    futures = {}
    futures["gemini"] = _search_executor.submit(_gemini_grounded_search, adapted_query)

    if mode == "news":
        futures["ddg"] = _search_executor.submit(_duckduckgo_news, adapted_query, 5)
    else:
        futures["ddg"] = _search_executor.submit(_duckduckgo_search, adapted_query, 5)

    for key, future in futures.items():
        try:
            result = future.result(timeout=15)
            if key == "gemini":
                gemini_result = result
            else:
                ddg_results = result or []
        except Exception as e:
            logger.warning(f"{key} search timed out or failed: {e}")

    # Prefer Gemini grounded search; fall back to DuckDuckGo
    if gemini_result:
        summary = gemini_result
        if ddg_results:
            summary += "\n\n---\nAdditional sources:\n"
            summary += _format_results(ddg_results[:3], mode)
        return summary

    if ddg_results:
        return _format_results(ddg_results, mode)

    return "I couldn't find any results for that query. Please try rephrasing."


def fetch_news(topic: str = "top news today") -> str:
    """Convenience function for pre-fetching news (startup briefing)."""
    return search_web(query=topic, mode="news")
