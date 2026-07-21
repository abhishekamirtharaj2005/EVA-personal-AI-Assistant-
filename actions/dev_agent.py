"""
EVA Dev Agent — Autonomous development agent with self-correcting error loop.
Run → capture output → parse traceback → classify error → feed back to Gemini for fix.
"""

import logging
import re
import subprocess
import traceback
from pathlib import Path
from typing import Optional

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.dev_agent")

_MAX_ITERATIONS = 5


def _run_command(cmd: str, cwd: str = ".") -> tuple[int, str, str]:
    """Run a development command and capture output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True,
            timeout=60, cwd=cwd,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out (60s limit)"
    except Exception as e:
        return -1, "", str(e)


def _parse_traceback(stderr: str) -> dict:
    """Parse a Python traceback to extract error info."""
    error_info = {
        "type": "unknown",
        "message": "",
        "file": "",
        "line": 0,
        "full_traceback": stderr[:2000],
    }

    # Python traceback
    tb_match = re.search(
        r'File "([^"]+)", line (\d+)',
        stderr
    )
    if tb_match:
        error_info["file"] = tb_match.group(1)
        error_info["line"] = int(tb_match.group(2))

    # Error type
    error_match = re.search(
        r"(\w+Error|\w+Exception|\w+Warning): (.+)",
        stderr
    )
    if error_match:
        error_info["type"] = error_match.group(1)
        error_info["message"] = error_match.group(2)

    # Node.js errors
    node_match = re.search(r"at (.+):(\d+):\d+", stderr)
    if node_match and not tb_match:
        error_info["file"] = node_match.group(1)
        error_info["line"] = int(node_match.group(2))

    return error_info


def _get_file_context(filepath: str, error_line: int,
                      context_lines: int = 10) -> str:
    """Get file content around the error line."""
    try:
        path = Path(filepath)
        if not path.exists():
            return ""

        lines = path.read_text(encoding="utf-8").splitlines()
        start = max(0, error_line - context_lines)
        end = min(len(lines), error_line + context_lines)

        context_parts = []
        for i in range(start, end):
            marker = " >>> " if i + 1 == error_line else "     "
            context_parts.append(f"{marker}{i + 1}: {lines[i]}")

        return "\n".join(context_parts)
    except Exception:
        return ""


def _ask_gemini_for_fix(error_info: dict, file_context: str,
                        original_task: str) -> str:
    """Ask Gemini to diagnose and suggest a fix."""
    try:
        import google.generativeai as genai
        from memory.config_manager import config

        genai.configure(api_key=config.get("api_key"))
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = (
            f"A development task encountered an error. Diagnose and provide a fix.\n\n"
            f"**Original Task**: {original_task}\n\n"
            f"**Error Type**: {error_info['type']}\n"
            f"**Error Message**: {error_info['message']}\n"
            f"**File**: {error_info['file']}\n"
            f"**Line**: {error_info['line']}\n\n"
            f"**Traceback**:\n```\n{error_info['full_traceback']}\n```\n\n"
        )

        if file_context:
            prompt += f"**Code Context** (>>> marks error line):\n```\n{file_context}\n```\n\n"

        prompt += (
            "Provide:\n"
            "1. Root cause diagnosis\n"
            "2. The exact fix (as a code diff or replacement)\n"
            "3. Any additional steps needed"
        )

        response = model.generate_content(prompt)
        return response.text if response else "No fix suggestion generated."
    except Exception as e:
        return f"Failed to get fix suggestion: {e}"


@register_tool(
    name="run_dev_task",
    description="Run a development command with automatic error detection and "
                "self-correcting fix suggestions. For multi-step dev tasks like "
                "running builds, tests, or scripts that might fail.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "command": {
                "type": "STRING",
                "description": "The command to run (e.g., 'python app.py', 'npm test')",
            },
            "working_directory": {
                "type": "STRING",
                "description": "Directory to run the command in",
            },
            "task_description": {
                "type": "STRING",
                "description": "Description of what this task should accomplish",
            },
            "auto_fix": {
                "type": "BOOLEAN",
                "description": "If true, attempt to diagnose errors and suggest fixes",
            },
        },
        "required": ["command"],
    },
    category="development",
)
def run_dev_task(command: str, working_directory: str = ".",
                 task_description: str = "", auto_fix: bool = True) -> str:
    """Run a development task with error handling and fix suggestions."""
    logger.info(f"Running dev task: {command} in {working_directory}")

    code, stdout, stderr = _run_command(command, cwd=working_directory)

    result_parts = [f"**Command**: `{command}`"]

    if stdout:
        result_parts.append(f"**Output**:\n```\n{stdout[:3000]}\n```")

    if code == 0:
        result_parts.append("✅ **Status**: Success")
        return "\n\n".join(result_parts)

    result_parts.append(f"❌ **Status**: Failed (exit code {code})")

    if stderr:
        result_parts.append(f"**Error**:\n```\n{stderr[:2000]}\n```")

    if auto_fix and stderr:
        error_info = _parse_traceback(stderr)
        file_context = ""
        if error_info["file"] and error_info["line"]:
            file_context = _get_file_context(
                error_info["file"], error_info["line"]
            )

        fix = _ask_gemini_for_fix(
            error_info, file_context,
            task_description or command
        )
        result_parts.append(f"**🔧 Suggested Fix**:\n{fix}")

    return "\n\n".join(result_parts)
