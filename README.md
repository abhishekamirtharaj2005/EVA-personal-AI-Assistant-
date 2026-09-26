# EVA — Enhanced Virtual Assistant

<p align="center">
  <img src="https://img.shields.io/badge/EVA-v2.0_Cyberpunk-00f0ff?style=for-the-badge&logo=electron&logoColor=black" alt="EVA">
  <img src="https://img.shields.io/badge/Gemini-3.8_Flash_Live_API-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Gemini 3.8 Flash">
  <img src="https://img.shields.io/badge/UI-PyQt6_HUD-41CD52?style=for-the-badge&logo=qt&logoColor=white" alt="PyQt6">
  <img src="https://img.shields.io/badge/Tools-53_Autonomous_Actions-ff007f?style=for-the-badge" alt="53 Tools">
  <img src="https://img.shields.io/badge/Platform-Windows_10%2F11-0078D6?style=for-the-badge&logo=windows&logoColor=white" alt="Windows">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
</p>

---

## ⚡ Overview

**EVA (Enhanced Virtual Assistant)** is an autonomous, real-time voice-activated AI desktop companion inspired by next-generation sci-fi interfaces and powered by Google's **Gemini 3.8 Flash Live API**. 

EVA operates via bidirectional, low-latency audio streaming: you talk, EVA listens, reasons, and speaks back naturally in real time. Backed by an extensible **53-tool autonomous action registry**, EVA can control your operating system, automate browser tasks, generate AI images, manage emails and Telegram messages, control IoT smart home devices, execute multi-agent developer swarms, manage finances, monitor hardware health, and adapt to custom personalities.

---

## ✨ Highlights & Key Capabilities

- 🎙️ **Real-Time Bidirectional Voice**: Zero push-to-talk required. Conversational voice interaction powered by Gemini 3.8 Flash with interruptibility, auto-reconnect backoff, and smart microphone hardware detection.
- 🗣️ **Wake Word Activation**: "Hey EVA" keyword spotting running in the background (lightweight transcript watcher + optional local neural net).
- 🌌 **High-Aesthetic Cyberpunk HUD**: Custom PyQt6 canvas with orbiting satellite nodes, segmented energy field arcs, live streaming data tickers, matrix glitch pulses, audio-reactive breathing aura, and segmented neon telemetry bars.
- 🛠️ **53 Registered Autonomous Tools**: Full system access ranging from mouse/keyboard automation, window switching, multi-monitor captures, file processing, and CLI dev tasks.
- 👁️ **Instant Vision & OCR**: Instant screen and webcam perception with zero-wait acknowledgments, plus OCR intelligence for extracting error codes, tracking numbers, and dialog texts.
- 🎨 **Creative Studio**: Generates AI artwork and wallpapers on voice demand with auto-setting desktop wallpaper.
- 🎵 **Media & Entertainment**: Native Spotify playback control, YouTube video launch with transcript extraction, and desktop screen recording with optional audio.
- 🏠 **Smart Home & IoT**: Seamless control over TP-Link Kasa smart plugs/lights and Home Assistant automations.
- 🤖 **Multi-Agent Swarms**: Deploys specialized sub-agents (Researcher, Coder, Reviewer, Planner) working concurrently on complex research and coding tasks.
- 📱 **Remote Phone Dashboard**: WebSockets + FastAPI dashboard accessible from any mobile device via secure QR code pairing and auto-generated SSL certificates.
- 🛡️ **Encrypted Password Vault**: Master PIN-protected local encrypted credentials storage with strong password generation.
- 🧠 **Dual-Layer Memory**: Long-term associative memory categorized across user preferences, lifestyle, and work habits, paired with auto-summarized session history.
- 🦙 **Local LLM Offline Fallback**: Seamless, transparent failover to local Ollama instances (Llama, Llava, Mistral) if offline or rate-limited.

---

## 🖥️ Cyberpunk UI & HUD Features

| UI Component | Description |
|---|---|
| **Orb HUD Canvas** | Vector-rendered canvas featuring dual-ring rotating data ticks, orbiting satellite nodes, particle fields, matrix data streams, and state-reactive breathing glow (Listening, Speaking, Thinking, Idle). |
| **Telemetry HUD Bars** | Segmented neon progress gauges displaying real-time CPU, RAM, GPU, and CPU Temperature metrics with animated shimmers and alarm thresholds. |
| **Terminal Activity Feed** | Terminal log widget with holographic color-coded source badges: `[EVA]`, `[USR]`, `[SYS]`, `[MOD]`, `[ERR]`. |
| **Interactive File Drop Zone** | Marching-ants dashed border with pulsing neon hover effects for drag-and-drop document analysis (PDF, PPTX, Images, Text). |
| **Customizer & Integrations** | Tabbed settings overlay supporting custom accent colors (Cyan, Green, Magenta, Orange, Purple), voice selection, API credentials, Email, Telegram, and Home Assistant integrations. |
| **Gaming Overlay Mode** | Minimalistic, borderless, semi-transparent HUD that floats over games and full-screen apps without taking focus or generating noisy popups. |

---

## 🧰 Autonomous Tool Catalog (53 Tools)

EVA's modular engine is organized across **44 action modules** registering **53 distinct tools**:

### 💻 System & Hardware Control
- **`get_system_stats`**: Telemetry reporting for CPU, RAM, GPU load, and hardware temperatures.
- **`open_application`**: Fuzzy name matching application launcher across Windows, Store/UWP apps, and utilities.
- **`close_application`**: Process terminator by executable name or window title.
- **`focus_window`**: Brings target window to foreground or enumerates open applications.
- **`multi_monitor`**: Multi-display awareness — per-monitor capture and cross-screen window movement.
- **`set_volume`**: Hardware audio volume control (0–100%) and mute toggling.
- **`set_brightness`**: Screen brightness adjustment.
- **`toggle_wifi`**: WiFi adapter status inspection and toggle.
- **`run_desktop_script`**: Sandboxed PowerShell automation runner.

### 🖱️ Input & UI Automation
- **`click_mouse`**: Pixel-precise mouse positioning, clicks, double clicks, and right clicks.
- **`type_text`**: Automated keyboard text entry.
- **`press_keys`**: Executes system shortcuts and hotkey combinations (`ctrl+c`, `alt+tab`, `win+d`).
- **`smart_clipboard`**: Analyzes clipboard content (JSON, URLs, code, addresses) and suggests instant actions.

### 👁️ Vision & Document Intelligence
- **`analyze_screen`**: Instant screenshot capture and multi-modal scene analysis.
- **`analyze_webcam`**: Webcam snapshot capture and user presence verification.
- **`ocr_extract`**: AI vision OCR for extracting error strings, code snippets, or document text.
- **`process_file`**: Multi-format document parser (PDF, PPTX, Markdown, Source Code, Images).
- **`manage_files`**: Safe file operations (create, read, write, move, rename, recycle bin delete).

### 🌐 Web & Knowledge Navigation
- **`open_browser`**: Launches and navigates real user browser sessions preserving existing logins.
- **`search_web`**: Multi-strategy web search (news, in-depth research, price comparison).
- **`get_weather`**: Real-time atmospheric conditions and forecasts.
- **`search_flights`**: Live flight search, pricing extraction, and route scheduling.
- **`location_service`**: Geolocation discovery, points of interest, traffic updates, and route distances.
- **`topic_monitor`**: Persistent background topic tracker alerting to daily breaking news.
- **`news_briefing`**: Tailored multi-category morning or evening news summaries.

### ✉️ Communications & Social
- **`manage_email`**: Read unread messages, search inbox, and compose emails via secure IMAP/SMTP.
- **`telegram`**: Two-way Telegram bot integration — inspect chats, broadcast messages, and configure auto-replies.
- **`send_message`**: UI-automated messaging through desktop WhatsApp and Telegram clients.
- **`phone_control`**: Mobile bridge via EVA's remote dashboard (sync notifications, file transfers, battery status).

### ⚡ Smart Home & IoT
- **`smart_home`**: Comprehensive IoT hub supporting TP-Link Kasa smart plugs/bulbs and Home Assistant REST entities (switches, lights, sensors, thermostats).

### 🎧 Media & Entertainment
- **`control_spotify`**: Play, pause, skip, queue tracks/playlists, search artists, and manage volume.
- **`play_youtube`**: Voice-activated YouTube playback and video transcript retrieval.
- **`screen_record`**: High-resolution screen video recording with optional voice narration saved directly to MP4.
- **`update_games`**: Steam game discovery, installation status inspection, and update triggering.

### 🚀 Developer Tools & Multi-Agent Swarms
- **`multi_agent`**: Spawns and coordinates specialized autonomous sub-agents (`researcher`, `coder`, `reviewer`, `planner`) working concurrently on complex goals.
- **`generate_code`**: Multi-language code generation, refactoring, and test authoring.
- **`review_code`**: Static code audit, vulnerability detection, and optimization advice.
- **`run_dev_task`**: Self-healing CLI command runner with automated error detection and fix proposals.

### 📅 Productivity, Health & Learning
- **`focus_mode`**: Distraction blocker with blacklisted process termination and focus timers.
- **`study_mode`**: Spaced-repetition flashcard system with quiz routines and progress tracking.
- **`manage_calendar`**: Schedule organizer for creating, listing, searching, and managing calendar events.
- **`track_expense`**: Voice-logged financial ledger with category breakdowns and periodic budgets.
- **`journal`**: Automated daily diary with Gemini-generated summaries and searchable history.
- **`health_tracker`**: Lifestyle tracking (water, sleep, steps, meals, weight, mood, screen break reminders).
- **`set_reminder`**: Persistent system toast reminders and scheduled alerts.
- **`show_analytics`**: Tool usage analytics, activity timelines, and productivity insights.

### 🔒 Security, Language & Personalization
- **`password_manager`**: Encrypted credentials locker protected by a master PIN with password generator.
- **`generate_image`**: AI image synthesis via Gemini Imagen / DALL-E with optional wallpaper setting.
- **`language_switch`**: Live conversational language switching (Hindi, Spanish, French, Japanese, German, etc.) and text translation.
- **`set_personality`**: Dynamically adjusts EVA's persona (`Default`, `Professional`, `Chill`, `Motivational`, `Sarcastic`, `Teacher`, `Pirate`).
- **`game_mode`**: Toggles distraction-free transparent gaming overlay.
- **`proactive_check`**: Internal proactive engine checking idle state to initiate helpful context-aware check-ins.

---

## 🏛️ Architecture & System Design

```
                     ┌──────────────────────────────────────────────┐
                     │          Microphone / Audio Output           │
                     └──────────────────────┬───────────────────────┘
                                            │ Bidirectional PCM
                                            ▼
┌───────────────────────┐            ┌──────────────────────────────┐
│  PyQt6 Cyberpunk UI   │◀──────────▶│     EVA Live Orchestrator    │
│  - HUD Canvas         │  Signals   │     (core/eva_live.py)       │
│  - Segmented Metrics  │            └──────────────┬───────────────┘
│  - Terminal Logs      │                           │
│  - Drop Zone          │                           ▼
└───────────────────────┘            ┌──────────────────────────────┐
           ▲                         │  Google Gemini 3.8 Flash     │
           │                         │  Live API (WebSocket Audio)  │
           ▼                         └──────────────┬───────────────┘
┌───────────────────────┐                           │ Function Calls
│  FastAPI Dashboard    │                           ▼
│  - WebSocket Server   │            ┌──────────────────────────────┐
│  - QR Phone Pairing   │            │   Tool Dispatcher Registry   │
└───────────────────────┘            │   - 53 Registered Tools      │
                                     │   - ThreadPool Executor      │
                                     └──────────────┬───────────────┘
                                                    │
                 ┌──────────────────────────────────┴──────────────────────────────────┐
                 ▼                                  ▼                                  ▼
      ┌─────────────────────┐            ┌─────────────────────┐            ┌─────────────────────┐
      │   Desktop & Input   │            │   Vision, Media,    │            │   IoT, Comms, &     │
      │   - Process Control │            │   & Creative        │            │   Productivity      │
      │   - Multi-Monitor   │            │   - Screen/Webcam   │            │   - Home Assistant  │
      │   - Mouse / Keys    │            │   - Spotify/YouTube │            │   - Telegram / Email│
      │   - Hardware Audio  │            │   - Imagen AI Art   │            │   - Multi-Agent Dev │
      └─────────────────────┘            └─────────────────────┘            └─────────────────────┘
```

---

## 📦 Requirements

- **Python**: 3.11 or higher
- **Operating System**: Windows 10/11 (fully supported; macOS & Linux supported for core/CLI features)
- **Audio**: Working microphone and speakers / headphones
- **Gemini API Key**: [Get a Gemini API Key](https://aistudio.google.com/apikey)
- *(Optional)* **Ollama**: For offline LLM fallback ([ollama.com](https://ollama.com))

---

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/abhishekamirtharaj2005/EVA-personal-AI-Assistant-.git
cd EVA
```

### 2. Create and Activate Virtual Environment
```bash
python -m venv venv
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate
```

### 3. Install Core Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install Windows Automation & Audio Dependencies (Windows)
```bash
pip install pycaw comtypes pywin32 pywinauto win10toast
```

### 5. Install Playwright Browsers (for web automation)
```bash
playwright install chromium
```

---

## ⚙️ Configuration

Copy the example configuration file:
```bash
cp config/settings.example.json config/settings.json
```

Or simply run EVA — the **Setup Wizard** will appear automatically on first launch:
```bash
python main.py
```

### Key Settings in `config/settings.json`:
| Parameter | Default | Description |
|---|---|---|
| `api_key` | `""` | Google Gemini API Key |
| `preferred_model` | `"gemini-3.8-flash"` | Gemini model used for the Live session |
| `voice_name` | `"Aoede"` | Voice profile (`Aoede`, `Charon`, `Fenrir`, `Kore`, `Puck`) |
| `accent_color` | `"#00f0ff"` | Cyberpunk HUD color (`#00f0ff`, `#32e632`, `#ff007f`, `#ffaa00`, `#9d4edd`) |
| `proactive_mode` | `true` | Enables idle conversation check-ins |
| `mic_device` | `null` | Index of preferred audio input device (`null` = auto-detect) |
| `ollama_enabled` | `false` | Enable local offline LLM fallback |
| `email_address` | `""` | Email for email manager integration |
| `telegram_bot_token`| `""` | Telegram bot token for two-way chat |
| `home_assistant_url`| `""` | Home Assistant instance URL |

---

## 🗣️ Voice Commands Cheatsheet

Once EVA is running, simply speak:

- **System**: *"What is my CPU and memory usage?"* • *"Turn the volume up to 80"* • *"Switch to VS Code"*
- **Vision**: *"Look at my screen and tell me what error this is"* • *"Read the text in this window"*
- **Media**: *"Play synthwave on Spotify"* • *"Search for quantum physics videos on YouTube"* • *"Start a screen recording"*
- **Creative**: *"Generate a wallpaper of a futuristic cyberpunk city at midnight and set it as my background"*
- **Developer**: *"Spawn a multi-agent team to plan and scaffold a FastAPI REST API"* • *"Review this Python file"*
- **Productivity**: *"Enter focus mode for 45 minutes"* • *"Quiz me with my chemistry flashcards"* • *"Log a 15 dollar lunch expense"*
- **Smart Home**: *"Turn on the desk lamp"* • *"Set thermostat to 72 degrees"*
- **Communications**: *"Check my unread emails"* • *"Send a Telegram message to Alex"*
- **Personality & Language**: *"Speak with a sarcastic personality"* • *"Speak in Spanish"*

---

## 📱 Mobile Remote Dashboard

Control EVA away from your desk via your smartphone:

1. Click the **📱 Remote** button in EVA's title bar or speak *"Open remote dashboard"*.
2. A cyberpunk QR code overlay will appear on screen.
3. Scan the QR code with your phone camera on the same Wi-Fi network.
4. Interact via the web app: send text commands, stream activity logs, inspect system telemetry, and share clipboard text.

---

## 🔒 Security & Privacy

- **Safe Configuration**: `config/settings.json`, conversation memory, recordings, and personal data are strictly ignored via `.gitignore`.
- **Encrypted Vault**: Credentials saved via `password_manager` are AES-encrypted using a user-selected master PIN.
- **Local Sandbox**: File management operations are restricted to user profile folders (Documents, Downloads, Desktop, Pictures, Videos) with reversible recycle-bin deletion.
- **Device Pairing**: The remote mobile dashboard generates ephemeral SSL certificates and requires matching token authentication.

---

## 🤝 Contributing

Contributions, feature requests, and bug reports are welcome!
1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is released under the [MIT License](LICENSE).
