"""
EVA File Processor — Type-sniffing file analysis.
Branches to image (Gemini vision), PDF, text/doc handling.
"""

import base64
import io
import logging
import mimetypes
from pathlib import Path

from core.tool_dispatcher import register_tool

logger = logging.getLogger("eva.actions.file_processor")


def _process_image(file_path: Path, prompt: str) -> str:
    """Analyze an image file with Gemini vision."""
    try:
        import google.generativeai as genai
        from memory.config_manager import config

        genai.configure(api_key=config.get("api_key"))
        model = genai.GenerativeModel("gemini-2.0-flash")

        image_data = file_path.read_bytes()
        mime = mimetypes.guess_type(str(file_path))[0] or "image/jpeg"
        b64 = base64.b64encode(image_data).decode("utf-8")

        response = model.generate_content([
            prompt or f"Describe and analyze this image: {file_path.name}",
            {"mime_type": mime, "data": b64},
        ])

        return response.text if response and response.text else "Image analyzed but no description generated."
    except Exception as e:
        return f"Image analysis failed: {e}"


def _process_pdf(file_path: Path, prompt: str) -> str:
    """Extract text from a PDF and optionally summarize."""
    try:
        # Try pdfplumber first, fall back to basic extraction
        text = ""
        try:
            import pdfplumber
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages[:20]:  # Limit pages
                    text += page.extract_text() or ""
                    text += "\n\n"
        except ImportError:
            # Fallback: use PyPDF2 or similar
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(file_path)
                for page in reader.pages[:20]:
                    text += page.extract_text() or ""
                    text += "\n\n"
            except ImportError:
                return "PDF processing requires pdfplumber or PyPDF2. Please install one."

        if not text.strip():
            return "PDF appears to be image-based (no extractable text). Try using screen capture."

        # Truncate for model context
        text = text[:8000]

        if prompt:
            # Use Gemini for analysis
            import google.generativeai as genai
            from memory.config_manager import config
            genai.configure(api_key=config.get("api_key"))
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                f"{prompt}\n\nDocument content:\n{text}"
            )
            return response.text if response else text

        return f"PDF Content ({file_path.name}):\n\n{text}"

    except Exception as e:
        return f"PDF processing failed: {e}"


def _process_text(file_path: Path, prompt: str) -> str:
    """Process a text-based file."""
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
        content = content[:8000]  # Truncate

        if prompt:
            import google.generativeai as genai
            from memory.config_manager import config
            genai.configure(api_key=config.get("api_key"))
            model = genai.GenerativeModel("gemini-2.0-flash")
            response = model.generate_content(
                f"{prompt}\n\nFile content ({file_path.name}):\n{content}"
            )
            return response.text if response else content

        return f"Content of {file_path.name}:\n\n{content}"

    except Exception as e:
        return f"Failed to read file: {e}"


@register_tool(
    name="process_file",
    description="Analyze a file's contents. Handles images (vision analysis), "
                "PDFs (text extraction + summarization), and text files. "
                "Use when a user drops a file or asks about file contents.",
    parameters={
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Path to the file to process",
            },
            "prompt": {
                "type": "STRING",
                "description": "What to do with the file (e.g., 'summarize', 'translate', 'analyze')",
            },
        },
        "required": ["file_path"],
    },
    category="files",
)
def process_file(file_path: str, prompt: str = "") -> str:
    """Process a file based on its type."""
    path = Path(file_path)
    if not path.exists():
        return f"File not found: {file_path}"

    mime = mimetypes.guess_type(str(path))[0] or ""
    suffix = path.suffix.lower()

    # Route by type
    image_exts = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tiff", ".svg"}
    text_exts = {".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json",
                 ".xml", ".yaml", ".yml", ".ini", ".cfg", ".log", ".csv", ".sh",
                 ".bat", ".ps1", ".java", ".cpp", ".c", ".h", ".rs", ".go"}

    if suffix in image_exts or mime.startswith("image/"):
        return _process_image(path, prompt)
    elif suffix == ".pdf" or mime == "application/pdf":
        return _process_pdf(path, prompt)
    elif suffix in text_exts or mime.startswith("text/"):
        return _process_text(path, prompt)
    elif suffix in {".docx", ".doc"}:
        return _process_text(path, prompt)  # Basic attempt
    else:
        return f"Unsupported file type: {suffix} ({mime or 'unknown'}). " \
               f"Supported: images, PDFs, text files."
