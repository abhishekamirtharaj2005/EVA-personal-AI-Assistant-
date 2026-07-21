"""
EVA — Enhanced Virtual Assistant
Main entrypoint.

Boots the PyQt6 UI on the main thread, starts the Gemini Live session
on a background asyncio thread, and launches the FastAPI dashboard server.
"""

import asyncio
import logging
import sys
import threading
from pathlib import Path

# ── Logging setup ───────────────────────────────────────────────

LOG_DIR = Path(__file__).parent / "config" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "eva.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("eva.main")


def main():
    """Main entrypoint."""
    # Set event loop policy BEFORE any threads are created
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    logger.info("=" * 60)
    logger.info("EVA — Enhanced Virtual Assistant starting...")
    logger.info("=" * 60)

    # ── 1. Load config ──────────────────────────────────────
    from memory.config_manager import config
    logger.info(f"Config loaded. First run: {config.is_first_run()}")

    # ── 2. Boot PyQt6 UI ────────────────────────────────────
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QIcon
    from PyQt6.QtCore import Qt

    app = QApplication(sys.argv)
    app.setApplicationName("EVA")
    app.setStyle("Fusion")  # Consistent cross-platform look

    from ui.main_window import MainWindow
    window = MainWindow()

    # ── 3. First-run setup ──────────────────────────────────
    if config.is_first_run():
        logger.info("First run detected — showing setup overlay")
        setup_overlay = window.show_setup_overlay()

        def on_setup_complete(api_key: str, user_name: str, assistant_name: str):
            config.complete_setup(api_key, user_name, assistant_name)
            setup_overlay.hide()
            window.update_title(assistant_name)
            logger.info(f"Setup complete: user={user_name}, assistant={assistant_name}")
            # Start the core engine after setup
            _start_core_engine(window)

        setup_overlay.setup_complete.connect(on_setup_complete)
    else:
        # Start core engine immediately
        _start_core_engine(window)

    # ── 4. Show window ──────────────────────────────────────
    window.show()
    logger.info("UI ready")

    # ── 5. Run Qt event loop ────────────────────────────────
    exit_code = app.exec()

    logger.info("EVA shutting down...")
    sys.exit(exit_code)


def _start_core_engine(window) -> None:
    """Start the Gemini Live engine and dashboard on background threads."""
    from core.eva_live import EvaLive

    eva_live = EvaLive(ui_signals=window)

    # ── Connect UI signals to engine ────────────────────────
    window.text_command_signal.connect(
        lambda text: eva_live.inject_text_command(text)
    )
    window.interrupt_signal.connect(
        lambda: eva_live.interrupt()
    )
    window.file_process_signal.connect(
        lambda path: eva_live.inject_text_command(
            f"A file was dropped for processing: {path}. "
            f"Please analyze it using the process_file tool."
        )
    )
    window.clipboard_action_signal.connect(
        lambda action, text: eva_live.inject_text_command(
            f"Please {action} the following text:\n\n{text[:1000]}"
        )
    )

    # ── Start background asyncio loop ───────────────────────
    def _run_async_loop():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(eva_live.start())
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.exception(f"Core engine error: {e}")
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            loop.close()

    engine_thread = threading.Thread(
        target=_run_async_loop, daemon=True, name="eva-engine"
    )
    engine_thread.start()
    logger.info("Core engine thread started")

    # ── Start dashboard server ──────────────────────────────
    try:
        from dashboard.server import start_dashboard_server, generate_pairing_key
        dashboard_thread = start_dashboard_server(eva_live)
        logger.info("Dashboard server thread started")

        # Generate initial pairing key and show on remote overlay
        key, url = generate_pairing_key()
        remote_overlay = window.get_remote_overlay()
        remote_overlay.show_pairing(key, url)
        remote_overlay.hide()  # Don't show automatically

        logger.info(f"Pairing key generated: {key}")
        logger.info(f"Dashboard URL: {url}")
        window.add_log_signal.emit(
            f"📱 Remote dashboard ready. Key: {key}", "system"
        )
    except Exception as e:
        logger.warning(f"Dashboard server failed to start: {e}")
        window.add_log_signal.emit(
            f"⚠ Dashboard failed: {e}", "error"
        )


if __name__ == "__main__":
    main()
