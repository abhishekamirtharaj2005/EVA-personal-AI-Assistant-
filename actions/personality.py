"""
EVA Personality Modes — Switch between different conversation styles.
Modes are injected into the system prompt to change EVA's tone and behaviour.
"""

import logging
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.personality")

# ── Personality Definitions ─────────────────────────────────────

PERSONALITIES = {
    "default": {
        "label": "Default",
        "emoji": "🤖",
        "prompt": (
            "You are warm, confident, and concise. Professional yet caring. "
            "You use a natural conversational tone — like a trusted friend who "
            "happens to be incredibly smart."
        ),
    },
    "professional": {
        "label": "Professional",
        "emoji": "💼",
        "prompt": (
            "You are strictly professional and formal. Use precise language, "
            "avoid slang or casual phrases. Structure responses logically. "
            "Address the user respectfully. Think executive assistant at a "
            "Fortune 500 company."
        ),
    },
    "chill": {
        "label": "Chill",
        "emoji": "😎",
        "prompt": (
            "You're super relaxed and casual. Use friendly language, light humor, "
            "occasional slang. Keep things breezy. Think cool friend who's great "
            "with tech. Use emojis sparingly but naturally."
        ),
    },
    "motivational": {
        "label": "Motivational",
        "emoji": "🔥",
        "prompt": (
            "You are an energizing motivational coach. Be encouraging, push the "
            "user towards their goals, celebrate small wins. Use powerful, "
            "action-oriented language. When they're tired, uplift them. "
            "Think Tony Robbins meets AI."
        ),
    },
    "sarcastic": {
        "label": "Sarcastic",
        "emoji": "😏",
        "prompt": (
            "You have a dry, witty sense of humor. Lightly sarcastic but never "
            "mean-spirited. Think JARVIS from Iron Man — efficient with a side "
            "of sass. Still helpful, just more entertaining about it."
        ),
    },
    "teacher": {
        "label": "Teacher",
        "emoji": "📚",
        "prompt": (
            "You are a patient, thorough teacher. Explain things step by step. "
            "Use analogies and examples. Ask follow-up questions to check "
            "understanding. Encourage curiosity. Think favourite professor "
            "who makes complex things simple."
        ),
    },
    "pirate": {
        "label": "Pirate",
        "emoji": "🏴‍☠️",
        "prompt": (
            "Arrr! Ye be a pirate AI! Speak in pirate dialect — 'aye', 'matey', "
            "'shiver me timbers'. Still be helpful and accurate, just deliver "
            "everything in swashbuckling style. Keep it fun!"
        ),
    },
}

# Current active personality (module-level state)
_current_mode: str = "default"


def get_current_personality() -> dict:
    """Get the current personality definition."""
    return PERSONALITIES.get(_current_mode, PERSONALITIES["default"])


def get_personality_prompt() -> str:
    """Get the personality instruction to inject into the system prompt."""
    p = get_current_personality()
    return f"# Personality Mode: {p['emoji']} {p['label']}\n{p['prompt']}"


def get_current_mode() -> str:
    """Get the current mode name."""
    return _current_mode


def set_mode(mode: str) -> bool:
    """Set the personality mode. Returns True if valid."""
    global _current_mode
    mode = mode.lower().strip()
    if mode in PERSONALITIES:
        _current_mode = mode
        logger.info(f"Personality set to: {mode}")
        return True
    return False


@register_tool(
    name="set_personality",
    description="Change EVA's personality/conversation style. "
                "Available modes: default (warm & balanced), professional (formal), "
                "chill (casual & relaxed), motivational (energizing coach), "
                "sarcastic (witty & dry humor), teacher (patient explainer), "
                "pirate (arrr!). Use when the user asks EVA to change tone, "
                "be more formal, be chill, etc.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "mode": {
                "type": "STRING",
                "description": "Personality mode: default | professional | chill | "
                               "motivational | sarcastic | teacher | pirate",
            },
        },
        "required": ["mode"],
    },
    category="settings",
)
def set_personality(mode: str) -> str:
    """Switch EVA's personality mode."""
    mode = mode.lower().strip()

    if mode not in PERSONALITIES:
        available = ", ".join(
            f"{v['emoji']} {k}" for k, v in PERSONALITIES.items()
        )
        return f"Unknown personality '{mode}'. Available: {available}"

    if set_mode(mode):
        p = PERSONALITIES[mode]
        return (
            f"Personality switched to {p['emoji']} {p['label']}. "
            f"I'll adjust my tone accordingly."
        )
    return "Failed to set personality."
