"""
EVA YouTube Video — Search, play, and get transcripts from YouTube.
"""

import logging
import re
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.youtube_video")


def _search_youtube(query: str) -> Optional[dict]:
    """Search YouTube and return the first matching video."""
    try:
        import requests
        from bs4 import BeautifulSoup

        url = f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)

        # Extract video IDs from the page
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', response.text)

        if video_ids:
            video_id = video_ids[0]
            # Try to extract title
            soup = BeautifulSoup(response.text, "html.parser")
            title = query  # Fallback

            return {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": title,
            }
    except Exception as e:
        logger.error(f"YouTube search failed: {e}")
    return None


def _get_transcript(video_id: str) -> Optional[str]:
    """Get a YouTube video transcript."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        transcripts = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([t["text"] for t in transcripts])
        return text[:5000]  # Truncate
    except Exception as e:
        logger.warning(f"Transcript fetch failed: {e}")
        return None


@register_tool(
    name="play_youtube",
    description="Search for and play a YouTube video, or get its transcript. "
                "Opens the video in the browser for playback.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "query": {
                "type": "STRING",
                "description": "Search query or YouTube URL",
            },
            "get_transcript": {
                "type": "BOOLEAN",
                "description": "If true, fetch and return the video transcript instead of playing",
            },
        },
        "required": ["query"],
    },
    category="media",
)
def play_youtube(query: str, get_transcript: bool = False) -> str:
    """Search for and play a YouTube video."""
    # Check if it's already a URL
    video_id = None
    if "youtube.com/watch" in query or "youtu.be/" in query:
        match = re.search(r"(?:v=|youtu\.be/)([a-zA-Z0-9_-]{11})", query)
        if match:
            video_id = match.group(1)

    if not video_id:
        result = _search_youtube(query)
        if not result:
            return f"No YouTube video found for: {query}"
        video_id = result["video_id"]
        video_url = result["url"]
    else:
        video_url = f"https://www.youtube.com/watch?v={video_id}"

    if get_transcript:
        transcript = _get_transcript(video_id)
        if transcript:
            return f"Transcript for video ({video_url}):\n\n{transcript}"
        return f"Transcript not available for this video. URL: {video_url}"

    # Open in browser
    import webbrowser
    webbrowser.open(video_url)
    return f"Playing YouTube video: {video_url}"
