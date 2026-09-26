"""
EVA Language Manager — Multi-language voice switching and translation.
Detects language changes and provides translation services.
"""

import logging
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.language_manager")

# Supported languages with their Gemini voice names
SUPPORTED_LANGUAGES = {
    "english": {"code": "en", "voice": "Charon", "greeting": "Hello"},
    "hindi": {"code": "hi", "voice": "Charon", "greeting": "नमस्ते"},
    "tamil": {"code": "ta", "voice": "Charon", "greeting": "வணக்கம்"},
    "telugu": {"code": "te", "voice": "Charon", "greeting": "నమస్కారం"},
    "spanish": {"code": "es", "voice": "Charon", "greeting": "Hola"},
    "french": {"code": "fr", "voice": "Charon", "greeting": "Bonjour"},
    "german": {"code": "de", "voice": "Charon", "greeting": "Hallo"},
    "japanese": {"code": "ja", "voice": "Charon", "greeting": "こんにちは"},
    "korean": {"code": "ko", "voice": "Charon", "greeting": "안녕하세요"},
    "chinese": {"code": "zh", "voice": "Charon", "greeting": "你好"},
    "arabic": {"code": "ar", "voice": "Charon", "greeting": "مرحبا"},
    "portuguese": {"code": "pt", "voice": "Charon", "greeting": "Olá"},
    "russian": {"code": "ru", "voice": "Charon", "greeting": "Привет"},
    "italian": {"code": "it", "voice": "Charon", "greeting": "Ciao"},
    "bengali": {"code": "bn", "voice": "Charon", "greeting": "নমস্কার"},
    "kannada": {"code": "kn", "voice": "Charon", "greeting": "ನಮಸ್ಕಾರ"},
    "malayalam": {"code": "ml", "voice": "Charon", "greeting": "നമസ്കാരം"},
    "marathi": {"code": "mr", "voice": "Charon", "greeting": "नमस्कार"},
    "gujarati": {"code": "gu", "voice": "Charon", "greeting": "નમસ્તે"},
}


@register_tool(
    name="language_switch",
    description="Switch EVA's conversation language, translate text, "
                "or detect the current language. Use when the user says "
                "'speak in Hindi', 'switch to Spanish', or 'translate this'.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "description": "Action: switch | translate | detect | list",
            },
            "language": {
                "type": "STRING",
                "description": "Target language for switch/translate. "
                               "E.g., 'hindi', 'spanish', 'japanese'",
            },
            "text": {
                "type": "STRING",
                "description": "Text to translate (for translate action)",
            },
        },
        "required": ["action"],
    },
    category="language",
)
def language_switch(action: str, language: str = "", text: str = "") -> str:
    """Manage language settings and translation."""
    action = action.lower().strip()

    if action == "switch":
        if not language:
            return "Which language should I switch to? Say a language name like 'Hindi', 'Spanish', etc."

        lang_lower = language.lower().strip()
        lang_info = SUPPORTED_LANGUAGES.get(lang_lower)

        if not lang_info:
            # Fuzzy match
            for name, info in SUPPORTED_LANGUAGES.items():
                if lang_lower in name or name in lang_lower:
                    lang_info = info
                    lang_lower = name
                    break

        if not lang_info:
            available = ", ".join(sorted(SUPPORTED_LANGUAGES.keys()))
            return f"Language '{language}' not recognized. Available: {available}"

        # Save to memory
        try:
            from memory.memory_manager import memory
            memory.remember("language", lang_lower, "identity")
        except Exception:
            pass

        # Save to config
        try:
            from memory.config_manager import config
            config.set("language", lang_lower)
        except Exception:
            pass

        return (
            f"🌍 Switched to {lang_lower.title()}! {lang_info['greeting']}!\n"
            f"I'll now respond in {lang_lower.title()}. "
            f"Say 'switch to English' to go back."
        )

    elif action == "translate":
        if not text:
            return "What should I translate?"
        if not language:
            return "Translate to which language?"

        # Use Gemini for translation
        try:
            from google import genai
            from memory.config_manager import config

            api_key = config.get("gemini_api_key", "") or config.get("api_key", "")
            if not api_key:
                return "Translation requires Gemini API key."

            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=f"Translate the following text to {language}. "
                         f"Only output the translation, nothing else:\n\n{text}",
            )
            translation = response.text.strip()
            return (
                f"🌍 Translation ({language.title()}):\n"
                f"   Original: {text}\n"
                f"   Translation: {translation}"
            )
        except Exception as e:
            return f"Translation failed: {e}"

    elif action == "detect":
        # Check current language setting
        current = "English"
        try:
            from memory.config_manager import config
            current = config.get("language", "english").title()
        except Exception:
            pass
        return f"🌍 Current language: {current}"

    elif action == "list":
        lines = []
        for name, info in sorted(SUPPORTED_LANGUAGES.items()):
            lines.append(f"  • {name.title()} ({info['code']}) — {info['greeting']}")
        return f"🌍 Supported languages ({len(SUPPORTED_LANGUAGES)}):\n" + "\n".join(lines)

    return f"Unknown language action '{action}'. Use: switch, translate, detect, list."
