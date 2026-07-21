"""
EVA Browser Control — Drives real browser profiles via Playwright.
Detects installed browsers and their profile directories per OS.
"""

import logging
import os
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool
from utils.platform_utils import IS_WINDOWS, IS_MACOS, IS_LINUX

logger = logging.getLogger("eva.actions.browser_control")

_browser_context = None
_browser_page = None


def _get_chrome_profile_dir() -> Optional[str]:
    """Find Chrome's real user profile directory."""
    if IS_WINDOWS:
        path = Path(os.environ.get("LOCALAPPDATA", "")) / "Google" / "Chrome" / "User Data"
    elif IS_MACOS:
        path = Path.home() / "Library" / "Application Support" / "Google" / "Chrome"
    else:
        path = Path.home() / ".config" / "google-chrome"

    return str(path) if path.exists() else None


def _get_edge_profile_dir() -> Optional[str]:
    """Find Edge's real user profile directory."""
    if IS_WINDOWS:
        path = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "Edge" / "User Data"
    elif IS_MACOS:
        path = Path.home() / "Library" / "Application Support" / "Microsoft Edge"
    else:
        path = Path.home() / ".config" / "microsoft-edge"

    return str(path) if path.exists() else None


def _get_firefox_profile_dir() -> Optional[str]:
    """Find Firefox's profile directory."""
    if IS_WINDOWS:
        path = Path(os.environ.get("APPDATA", "")) / "Mozilla" / "Firefox" / "Profiles"
    elif IS_MACOS:
        path = Path.home() / "Library" / "Application Support" / "Firefox" / "Profiles"
    else:
        path = Path.home() / ".mozilla" / "firefox"

    if path.exists():
        # Find default profile
        for p in path.iterdir():
            if p.is_dir() and ("default" in p.name.lower() or "release" in p.name.lower()):
                return str(p)
        # Return first profile if no default found
        for p in path.iterdir():
            if p.is_dir():
                return str(p)
    return None


async def _get_or_create_browser():
    """Get or create a Playwright browser context with real profile."""
    global _browser_context, _browser_page

    if _browser_page is not None:
        try:
            # Check if page is still alive
            await _browser_page.title()
            return _browser_page
        except Exception:
            _browser_page = None
            _browser_context = None

    from playwright.async_api import async_playwright

    pw = await async_playwright().start()

    # Try Chrome first, then Edge, then Firefox
    chrome_dir = _get_chrome_profile_dir()
    edge_dir = _get_edge_profile_dir()

    if chrome_dir:
        browser = await pw.chromium.launch_persistent_context(
            user_data_dir=chrome_dir,
            channel="chrome",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        logger.info("Using Chrome with real profile")
    elif edge_dir:
        browser = await pw.chromium.launch_persistent_context(
            user_data_dir=edge_dir,
            channel="msedge",
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        logger.info("Using Edge with real profile")
    else:
        browser = await pw.chromium.launch_persistent_context(
            user_data_dir="",
            headless=False,
        )
        logger.info("Using default Chromium (no real profile found)")

    _browser_context = browser
    _browser_page = browser.pages[0] if browser.pages else await browser.new_page()
    return _browser_page


@register_tool(
    name="open_browser",
    description="Open a URL in the browser using the user's real browser profile "
                "(so existing logins carry over). Can also search Google.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "url": {
                "type": "STRING",
                "description": "URL to open, or a search query (will be Google-searched)",
            },
            "wait_for_load": {
                "type": "BOOLEAN",
                "description": "Whether to wait for the page to fully load (default true)",
            },
        },
        "required": ["url"],
    },
    category="browser",
)
async def open_browser(url: str, wait_for_load: bool = True) -> str:
    """Open a URL in the browser with the real user profile."""
    # If it's a search query (no dots or protocol), search Google
    if not any(c in url for c in [".", "://", "localhost"]):
        url = f"https://www.google.com/search?q={url.replace(' ', '+')}"
    elif not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        page = await _get_or_create_browser()
        await page.goto(url, wait_until="domcontentloaded" if wait_for_load else "commit")
        title = await page.title()
        return f"Opened: {title} ({url})"
    except Exception as e:
        logger.error(f"Browser navigation failed: {e}")
        # Fallback: open with system browser
        import webbrowser
        webbrowser.open(url)
        return f"Opened in system browser: {url}"


async def get_page_content(url: str = None) -> str:
    """Get the text content of the current or specified page."""
    try:
        page = await _get_or_create_browser()
        if url:
            await page.goto(url, wait_until="domcontentloaded")
        content = await page.inner_text("body")
        return content[:5000]  # Truncate for model context
    except Exception as e:
        return f"Failed to get page content: {e}"


async def close_browser() -> None:
    """Close the browser context."""
    global _browser_context, _browser_page
    if _browser_context:
        await _browser_context.close()
        _browser_context = None
        _browser_page = None
