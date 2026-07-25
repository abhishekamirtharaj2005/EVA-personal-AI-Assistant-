# EVA — Enhanced Virtual Assistant

<p align="center">
  <strong>A cyberpunk-styled AI desktop assistant powered by Gemini Live API</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=flat-square&logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Gemini-Live_API-4285F4?style=flat-square&logo=google" alt="Gemini">
  <img src="https://img.shields.io/badge/UI-PyQt6-41CD52?style=flat-square" alt="PyQt6">
  <img src="https://img.shields.io/badge/platform-Windows-0078D6?style=flat-square&logo=windows" alt="Windows">
</p>

---

## Overview

EVA is a real-time voice assistant that runs on your desktop. It connects to **Google Gemini Live API** for bidirectional audio streaming — you talk, EVA listens, thinks, and speaks back. It can control your computer, browse the web, manage files, play YouTube, check weather, and much more through **27 built-in action modules**.

### Key Features

- 🎙️ **Real-time voice conversation** via Gemini Live bidirectional audio
- 🖥️ **Desktop control** — open apps, press keys, click, type, manage windows
- 🌐 **Web browsing** — search, navigate, and extract content with Playwright
- 📱 **Remote dashboard** — control EVA from your phone via QR pairing
- 📊 **System monitoring** — CPU, RAM, GPU, temperature with alert thresholds
- 📂 **File management** — read, write, move, trash files with drag-and-drop
- 🎬 **Media playback** — play YouTube videos by voice command
- ⏰ **Reminders & timers** — schedule notifications with custom messages
- 🔧 **Code generation** — scaffold code, review files, run dev tasks
- 🧠 **Proactive mode** — EVA can initiate conversation when you're idle
- 🎨 **Cyberpunk UI** — neon glows, hex grid, scanlines, animated HUD orb

---

## Screenshots

The UI features a cyberpunk aesthetic with:
- Animated HUD orb with hex grid background and floating particles
- Neon-styled metric bars (`CPU // 43%`)
- Terminal-style activity log with `[USR]`, `[EVA]`, `[SYS]`, `[MOD]` prefixes
- Full settings panel with 4 tabs (API Keys, Voice & Model, Appearance, System)

---

## Requirements

- **Python** 3.11+
- **OS**: Windows 10/11 (primary target)
- **Google Gemini API Key** — [Get one here](https://aistudio.google.com/apikey)
- **Microphone & speakers** for voice interaction

---

## Installation

```bash
# Clone the repository
git clone https://github.com/abhishekamirtharaj2005/EVA-personal-AI-Assistant-.git
cd EVA

# Install dependencies
pip install -r requirements.txt

# Windows-specific extras
pip install pycaw comtypes pywin32 pywinauto win10toast

# Install Playwright browsers (for web actions)
playwright install chromium
```

---

## Quick Start

```bash
python main.py
```

On first run, EVA will show a **setup wizard** to enter your API key and preferences.

### Configuration

All settings are stored in `config/settings.json` and can be changed via the **Settings panel** (⚙ button) at any time:

| Setting | Description |
|---------|-------------|
| **API Keys** | Gemini (primary), OpenAI, Anthropic |
| **Model** | `gemini-3.1-flash-live-preview` (default) |
| **Voice** | Aoede, Charon, Fenrir, Kore, Puck |
| **Proactive Mode** | Auto-engage after idle (default: 5 min) |
| **Morning Briefing** | Greeting on startup |
| **System Alerts** | CPU/RAM/GPU/Temp thresholds |
| **City** | For weather reports |

---

## Project Structure

```
EVA/
├── main.py                 # Application entrypoint
├── requirements.txt        # Python dependencies
├── config/                 # Runtime config & data
│   ├── settings.json       # User settings (API keys, preferences)
│   ├── memory.json         # Conversation memory
│   ├── certs/              # SSL certificates for dashboard
│   ├── logs/               # Application logs
│   ├── reminders/          # Scheduled reminders
│   └── uploads/            # File upload staging
├── core/                   # Engine core
│   ├── eva_live.py         # Gemini Live session orchestrator
│   ├── audio_manager.py    # Mic input + speaker output streams
│   ├── tool_registry.py    # Tool declaration & dispatch
│   └── system_prompt.py    # AI system prompt builder
├── actions/                # 19 action modules (27 tools)
│   ├── browser_control.py  # Web browsing via Playwright
│   ├── computer_control.py # Mouse, keyboard, windows
│   ├── computer_settings.py# Volume, brightness, WiFi, wallpaper
│   ├── code_helper.py      # Code generation & scaffolding
│   ├── desktop.py          # Desktop scripting (PowerShell)
│   ├── dev_agent.py        # Developer workflow automation
│   ├── file_controller.py  # File management (read/write/move)
│   ├── file_processor.py   # Document processing (PDF, PPTX)
│   ├── flight_finder.py    # Flight search
│   ├── game_updater.py     # Steam/Epic game updates
│   ├── open_app.py         # Application launcher
│   ├── proactive.py        # Idle-triggered engagement
│   ├── reminder.py         # Timers & scheduled reminders
│   ├── screen_processor.py # Screenshot analysis via Gemini
│   ├── send_message.py     # Email & messaging
│   ├── system_monitor.py   # CPU/RAM/GPU/Temp metrics
│   ├── weather_report.py   # Weather via web search
│   ├── web_search.py       # DuckDuckGo + Gemini grounded search
│   └── youtube_video.py    # YouTube playback & transcripts
├── ui/                     # PyQt6 cyberpunk interface
│   ├── styles.py           # Theme system (neon palette, fonts)
│   ├── main_window.py      # Main application window
│   ├── hud_canvas.py       # Animated orb with hex grid
│   ├── log_widget.py       # Terminal-style activity log
│   ├── metric_bar.py       # System metrics HUD bars
│   ├── customize_overlay.py# Settings panel (4 tabs)
│   ├── setup_overlay.py    # First-run wizard
│   ├── remote_key_overlay.py# QR pairing overlay
│   ├── file_drop_zone.py   # Drag-and-drop file zone
│   ├── camera_preview.py   # Webcam preview widget
│   └── clipboard_panel.py  # Clipboard action panel
├── dashboard/              # Remote phone dashboard (WebSocket)
│   ├── server.py           # FastAPI + WebSocket server
│   └── static/             # Web client (HTML/CSS/JS)
├── memory/                 # Persistence layer
│   └── config_manager.py   # JSON-backed settings store
└── utils/                  # Shared utilities
    └── helpers.py          # Common helper functions
```

---

## Action Modules

| Module | Tools | Description |
|--------|-------|-------------|
| `browser_control` | `open_browser` | Navigate URLs, search, extract content |
| `computer_control` | `click_mouse`, `press_keys`, `type_text`, `focus_window` | Desktop automation |
| `computer_settings` | `set_volume`, `set_brightness`, `toggle_wifi`, `set_wallpaper` | System settings |
| `code_helper` | `generate_code`, `review_code` | Code scaffolding & review |
| `desktop` | `run_desktop_script` | PowerShell script execution |
| `dev_agent` | `run_dev_task` | Developer workflow automation |
| `file_controller` | `manage_files` | File CRUD operations |
| `file_processor` | `process_file` | PDF, PPTX, text analysis |
| `flight_finder` | `search_flights` | Flight search |
| `game_updater` | `update_games` | Steam/Epic game management |
| `open_app` | `open_application` | Application launcher |
| `proactive` | `proactive_check` | Idle engagement engine |
| `reminder` | `set_reminder` | Timers & reminders |
| `screen_processor` | `analyze_screen`, `analyze_webcam` | Vision analysis |
| `send_message` | `send_message` | Email & messaging |
| `system_monitor` | `get_system_stats` | System telemetry |
| `weather_report` | `get_weather` | Weather lookup |
| `web_search` | `search_web` | Web search (DuckDuckGo + Gemini) |
| `youtube_video` | `play_youtube` | YouTube playback |

---

## Remote Dashboard

EVA includes a phone-accessible dashboard via WebSocket:

1. Click the 📱 button in the app
2. Scan the QR code with your phone
3. Control EVA remotely — send text commands, view logs, monitor metrics

The dashboard runs on `https://0.0.0.0:8765` with auto-generated SSL certificates.

---

## License

This project is for personal/educational use.

---

## Acknowledgments

- [Google Gemini Live API](https://ai.google.dev/gemini-api/docs/live) — real-time bidirectional AI
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) — desktop UI framework
- [Playwright](https://playwright.dev/) — browser automation
