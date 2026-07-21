"""
EVA Code Helper — Gemini-powered code generation, review, and editing.
"""

import logging
import re
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.code_helper")


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from generated code."""
    # Remove ```language\n...\n```
    text = re.sub(r"```\w*\n", "", text)
    text = re.sub(r"\n```$", "", text.strip())
    text = re.sub(r"```$", "", text.strip())
    return text.strip()


def _gemini_code_request(prompt: str) -> str:
    """Send a code-related request to Gemini."""
    try:
        import google.generativeai as genai
        from memory.config_manager import config

        genai.configure(api_key=config.get("api_key"))
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(prompt)
        return response.text if response and response.text else "No response generated."
    except Exception as e:
        return f"Code generation failed: {e}"


@register_tool(
    name="generate_code",
    description="Generate code in any programming language using Gemini AI. "
                "Can also explain code, write unit tests, or convert between languages.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "prompt": {
                "type": "STRING",
                "description": "Description of the code to generate",
            },
            "language": {
                "type": "STRING",
                "description": "Programming language (e.g., 'python', 'javascript')",
            },
            "save_to": {
                "type": "STRING",
                "description": "Optional file path to save the generated code",
            },
        },
        "required": ["prompt"],
    },
    category="development",
)
def generate_code(prompt: str, language: str = "", save_to: str = "") -> str:
    """Generate code using Gemini."""
    full_prompt = f"Generate clean, production-quality code"
    if language:
        full_prompt += f" in {language}"
    full_prompt += f".\n\nRequirement: {prompt}\n\n"
    full_prompt += "Provide ONLY the code, no explanations. Use proper formatting and comments."

    result = _gemini_code_request(full_prompt)
    code = _strip_markdown_fences(result)

    if save_to:
        try:
            path = Path(save_to)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(code, encoding="utf-8")
            preview = code[:200] + "..." if len(code) > 200 else code
            return f"Code saved to {save_to}\n\nPreview:\n```\n{preview}\n```"
        except Exception as e:
            return f"Generated code but failed to save: {e}\n\nCode:\n```\n{code}\n```"

    return f"```{language or ''}\n{code}\n```"


@register_tool(
    name="review_code",
    description="Review, analyze, or critique code. Provides suggestions for "
                "improvements, bug detection, and best practices.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "code": {
                "type": "STRING",
                "description": "The code to review (or file path to read)",
            },
            "focus": {
                "type": "STRING",
                "description": "What to focus on: 'bugs', 'performance', 'security', "
                               "'style', 'general'",
            },
        },
        "required": ["code"],
    },
    category="development",
)
def review_code(code: str, focus: str = "general") -> str:
    """Review code and provide feedback."""
    # Check if it's a file path
    path = Path(code)
    if path.exists() and path.is_file():
        try:
            code = path.read_text(encoding="utf-8")[:8000]
        except Exception:
            pass

    focus_map = {
        "bugs": "Find potential bugs, edge cases, and error handling issues",
        "performance": "Identify performance bottlenecks and optimization opportunities",
        "security": "Check for security vulnerabilities and unsafe patterns",
        "style": "Review code style, naming conventions, and readability",
        "general": "Provide a comprehensive code review covering bugs, performance, style, and improvements",
    }

    focus_instruction = focus_map.get(focus, focus_map["general"])

    prompt = (
        f"Review the following code. {focus_instruction}.\n\n"
        f"Provide actionable feedback with specific line references "
        f"and suggested improvements.\n\n"
        f"Code:\n```\n{code}\n```"
    )

    return _gemini_code_request(prompt)
