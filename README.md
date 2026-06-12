# Ditado

> **Dictation** — Portuguese speech-to-text for Windows, with 13 languages + auto-detect.
> Press F8, speak, and text is transcribed and pasted into any application.
> Built for fast note-taking with AI agents, Notion, and Obsidian.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

---

## Why Ditado?

I created Ditado to **speed up how I interact with AI agents and capture my thoughts**.

I frequently use tools like Notion, Obsidian, and AI chat interfaces for brainstorming and note-taking, but typing was always the bottleneck. My mind moves faster than my fingers.

I tried existing solutions like **Wispr Flow** and other dictation tools, but none fully met my needs — they required subscriptions, sent audio to the cloud, or didn't support Portuguese well. So I built my own: a lightweight, offline-first dictation app tailored for Portuguese speakers.

Ditado lets me externalize my thoughts 3-4x faster than typing, directly into any text field, with full privacy.

---

## Features

- **F8 hotkey** — toggle recording from any application
- **13 languages** — switch between Portuguese (default), English, Spanish, French, German, Italian, Dutch, Japanese, Chinese, Russian, Arabic, Korean, or auto-detect via the tray menu
- **Fully offline** — audio never leaves your machine; uses faster-whisper locally
- **Auto-paste** — transcribed text is automatically pasted via Ctrl+V
- **System tray** — runs quietly in the background with a microphone icon
- **Startup option** — toggle "Run at Windows Startup" from the tray menu

---

## Comparison

| Feature | Ditado | Wispr Flow | Dictly | freewispr | OpenWhispr |
|---------|--------|------------|--------|-----------|------------|
| **Price** | Free (MIT) | $12/mo | Free (MIT) | Free (MIT) | Free (MIT) |
| **Open Source** | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Offline (local model)** | ✅ | ❌ (cloud) | ✅ | ✅ | ✅ |
| **Privacy** | ✅ 100% local | ❌ cloud processing | ✅ 100% local | ✅ 100% local | ✅ local option |
| **Portuguese support** | ✅ default | ✅ 100+ langs | ✅ 99 langs | ✅ 99 langs | ✅ 100+ langs |
| **Language selector** | ✅ tray menu | ❌ auto only | ✅ settings | ✅ settings | ✅ settings |
| **Platform** | Windows | Mac, Windows, iOS, Android | Windows | Windows | Mac, Windows, Linux |
| **Install size** | ~110 MB | ~1 GB+ | ~150 MB | ~110 MB | ~200 MB |
| **Hotkey** | F8 toggle | Push-to-talk | Push-to-talk | Push-to-talk | Push-to-talk |
| **Text cleanup** | ❌ (raw Whisper) | ✅ AI cleanup | ❌ | ✅* | ❌ |

---

## Quick Start

```bash
pip install faster-whisper sounddevice numpy pyperclip pystray pillow
python ditado.py
```

Press **F8** to start recording, press **F8** again to transcribe and paste.

> **Note:** The first run downloads the Whisper model (~500 MB). Subsequent launches are instant.

---

## Usage

1. Run `python ditado.py` — the app hides its console and appears in the system tray
2. Press **F8** — the icon turns red and a notification confirms recording
3. Speak (in any of the 13 supported languages)
4. Press **F8** again — audio is transcribed and the text is pasted into the active window
5. For longer recordings, **transcription may take a few minutes** — wait for the paste notification
6. Right-click the tray icon to:
   - **Stop Recording** / **Start Recording**
   - **Language** — select from 13 languages or auto-detect
   - **Run at Windows Startup**
   - **Quit**

---

## Language Support

Switch languages at any time from the tray menu **Language** submenu:

| Language | Code |
|----------|------|
| Auto-detect | (automatic) |
| Português | `pt` (default) |
| English | `en` |
| Español | `es` |
| Français | `fr` |
| Deutsch | `de` |
| Italiano | `it` |
| Nederlands | `nl` |
| 日本語 | `ja` |
| 中文 | `zh` |
| Русский | `ru` |
| العربية | `ar` |
| 한국어 | `ko` |

> The underlying Whisper model supports **99+ languages** — open an issue if you need one not listed.

---

## Downloads

| Package | Size | Description |
|---------|------|-------------|
| [`Ditado-Installer-1.0.0.exe`](https://github.com/erickguedes/ditado/releases) | ~112 MB | Inno Setup installer — installs to Program Files, creates Start Menu & Desktop shortcuts, adds uninstaller |
| [`ditado.exe`](https://github.com/erickguedes/ditado/releases) | ~110 MB | Portable standalone .exe — no install needed, just run |

> The Whisper model (~500 MB) is downloaded on first launch automatically.

---

## Requirements

- Windows 10 or 11
- Python 3.10+ (if running from source)
- Microphone

---

## Build from Source

```bash
pip install pyinstaller
pyinstaller ditado.spec          # → dist/ditado.exe
python build.py                  # or use the helper script
python build.py --installer      # + Inno Setup installer (requires iscc.exe)
```

---

## License

MIT
