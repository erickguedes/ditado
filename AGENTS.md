# Ditado — agent instructions

Single-file Windows system-tray dictation app (`ditado.py`). Portuguese speech-to-text via faster-whisper, pasted via simulated Ctrl+V.

## Commands

```bash
# Run from source
pip install faster-whisper sounddevice numpy pyperclip pystray pillow
python ditado.py

# Build standalone .exe
pip install pyinstaller
pyinstaller ditado.spec
```

## Architecture

- **Windows-only** (`ctypes.windll`, Win32 hotkeys `RegisterHotKey`/`GetMessageW`, COM startup shortcuts)
- Hides console via `FreeConsole`; runs as systray icon via `pystray`
- Hotkey: **F8** toggles recording (no modifiers, message pump in daemon thread)
- Audio: continuous `sounddevice.InputStream` at 16kHz mono; `_recording` flag gates accumulation in `_audio_chunks`
- Model: `faster-whisper` `small` on CPU with `int8` compute (first-run downloads ~500 MB)
- Language: hardcoded `"pt"` (Portuguese)
- On stop: writes temp `.wav`, transcribes in daemon thread, copies text to clipboard, simulates Ctrl+V (`keybd_event` 0x11→0x56) into active window, shows 60-char notification preview, deletes temp file
- Startup toggle: creates `.lnk` via `powershell -Command` with `WScript.Shell`, uses `pythonw.exe` to avoid console

## Key details

- `os._exit(0)` for clean quit (bypasses `pystray` cleanup)
- `pystray.MenuItem` uses `checked` lambda for startup-toggle state
- Hotkey thread is daemon; main thread runs `_icon.run()` (systray event loop)
- `subprocess.CREATE_NO_WINDOW` flag for startup shortcut PowerShell call
- Icon rendered programmatically via `PIL.ImageDraw` in `create_icon()` (no resource file)

## AIOX agents

AIOX-core agents are available via `.codex/skills/`. Activate with:

```
/aiox-dev       # Developer (Dex) - code implementation
/aiox-qa        # QA (Quinn) - testing, code review
/aiox-architect # Architect (Aria) - system design
/aiox-pm        # PM (Morgan) - product strategy, planning
/aiox-analyst   # Analyst (Alex) - business analysis
/aiox-devops    # DevOps (Gage) - CI/CD, git ops
/aiox-master    # Orchestrator (Pax) - framework orchestration
```

## Installer build

```bash
python build.py            # PyInstaller .exe
python build.py --installer # .exe + Inno Setup installer (requires iscc.exe)
```
