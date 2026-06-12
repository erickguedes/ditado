"""Ditado — Windows speech-to-text dictation app.

Press F8 to record, press F8 again to transcribe and paste
the result into the active window via simulated Ctrl+V.
"""

import ctypes
import os
import subprocess
import sys
import tempfile
import threading
import time
import wave
from ctypes import wintypes

import numpy as np
import pyperclip
import pystray
import sounddevice as sd
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw

user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
VK_F8 = 0x77
MOD_NOREPEAT = 0x4000

MODEL_SIZE = "small"

LANGUAGES = {
    "":   "Auto-detect",
    "pt": "Portugu\u00eas",
    "en": "English",
    "es": "Espa\u00f1ol",
    "fr": "Fran\u00e7ais",
    "de": "Deutsch",
    "it": "Italiano",
    "nl": "Nederlands",
    "ja": "\u65e5\u672c\u8a9e",
    "zh": "\u4e2d\u6587",
    "ru": "\u0420\u0443\u0441\u0441\u043a\u0438\u0439",
    "ar": "\u0627\u0644\u0639\u0631\u0628\u064a\u0629",
    "ko": "\ud55c\uad6d\uc5b4",
}

_language = "pt"

_recording = False
_audio_chunks = []
_icon = None
_model = None
_hotkey_thread_running = True


def hide_console():
    """Detach the console so the app runs silently in the background."""
    try:
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


def create_icon(recording):
    """Render a 64x64 microphone icon: red when recording, grey when idle."""
    size = (64, 64)
    color = (220, 50, 50) if recording else (140, 140, 140)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([20, 8, 44, 36], radius=8, fill=color)
    for y in range(16, 33, 4):
        draw.rectangle([24, y, 40, y + 1], fill=(255, 255, 255, 60))
    draw.rectangle([29, 36, 35, 46], fill=color)
    draw.rectangle([20, 44, 44, 48], fill=color)
    return img


def audio_callback(indata, frames, time_info, status):
    """Accumulate raw audio chunks into _audio_chunks while recording is active."""
    if _recording:
        _audio_chunks.append(indata.copy())


def transcribe():
    """Transcribe accumulated audio, copy to clipboard, and simulate Ctrl+V paste."""
    global _recording, _audio_chunks
    if not _audio_chunks:
        return
    audio = np.concatenate(_audio_chunks, axis=0)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name
    try:
        with wave.open(wav_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(16000)
            audio_int16 = (audio * 32767).astype("int16")
            wf.writeframes(audio_int16.tobytes())
        lang = _language if _language else None
        segments, _ = _model.transcribe(wav_path, language=lang, beam_size=5)
        text = " ".join(s.text.strip() for s in segments)
        if text.strip():
            pyperclip.copy(text)
            # Simulate Ctrl+V: press Ctrl, press V, release V, release Ctrl
            time.sleep(0.15)
            user32.keybd_event(0x11, 0, 0, 0)
            user32.keybd_event(0x56, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(0x56, 0, 2, 0)
            user32.keybd_event(0x11, 0, 2, 0)
            if _icon:
                preview = text[:60] + ("..." if len(text) > 60 else "")
                _icon.notify(f'Pasted: "{preview}"', "Ditado")
    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass


def start_recording():
    """Begin audio capture and update the tray icon to red."""
    global _recording, _audio_chunks
    _audio_chunks = []
    _recording = True
    if _icon:
        _icon.icon = create_icon(True)
        _icon.notify("Recording... Press F8 to stop", "Ditado")


def stop_recording():
    """Stop audio capture and launch transcription in a daemon thread."""
    global _recording
    _recording = False
    if _icon:
        _icon.icon = create_icon(False)
        _icon.notify("Processing audio (may take a minute for longer recordings)...", "Ditado")
    threading.Thread(target=transcribe, daemon=True).start()


def toggle_recording():
    """Start or stop recording based on current state."""
    if _recording:
        stop_recording()
    else:
        start_recording()


def hotkey_listener():
    """Run a Win32 message pump in a daemon thread to detect F8 hotkey presses."""
    global _hotkey_thread_running
    user32.RegisterHotKey(None, 1, 0, VK_F8)
    msg = wintypes.MSG()
    while _hotkey_thread_running:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == 0:
            break
        if msg.message == WM_HOTKEY:
            toggle_recording()
    user32.UnregisterHotKey(None, 1)


def startup_shortcut_path():
    """Return the path to the Windows Startup shortcut for auto-launch."""
    return os.path.join(
        os.environ["APPDATA"],
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
        "Ditado.lnk",
    )


def is_startup_enabled():
    """Check whether the Ditado Startup shortcut exists."""
    return os.path.exists(startup_shortcut_path())


def toggle_startup():
    """Create or remove the Windows Startup shortcut."""
    shortcut = startup_shortcut_path()
    if is_startup_enabled():
        os.remove(shortcut)
    else:
        pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
        if not os.path.exists(pythonw):
            pythonw = sys.executable
        script = os.path.abspath(__file__)
        workdir = os.path.dirname(script)
        ps = f"""
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut('{shortcut}')
$s.TargetPath = '"{pythonw}"'
$s.Arguments = '"{script}"'
$s.WorkingDirectory = '"{workdir}"'
$s.Description = 'Ditado - Speech-to-Text'
$s.Save()
"""
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )


def set_language(code):
    """Change the transcription language at runtime."""
    global _language
    _language = code
    if _icon:
        name = LANGUAGES.get(code, code)
        _icon.notify(f"Language: {name}", "Ditado")


def language_menu():
    """Build the language submenu with radio-style checked items."""
    items = []
    for code, name in LANGUAGES.items():
        items.append(
            pystray.MenuItem(
                name,
                lambda _, c=code: set_language(c),
                checked=lambda _, c=code: _language == c,
                radio=True,
            )
        )
    return pystray.Menu(*items)


def create_menu():
    """Build the system-tray right-click menu."""
    return pystray.Menu(
        pystray.MenuItem(
            lambda item: "⏹ Stop Recording" if _recording else "🎤 Start Recording",
            toggle_recording,
            default=True,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            "Run at Windows Startup",
            toggle_startup,
            checked=lambda item: is_startup_enabled(),
        ),
        pystray.MenuItem(
            "Language",
            language_menu(),
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", quit_app),
    )


def quit_app():
    """Cleanly shut down the hotkey thread, systray icon, and process."""
    global _hotkey_thread_running
    _hotkey_thread_running = False
    if _icon:
        _icon.stop()
    os._exit(0)


def main():
    """Initialize model, systray icon, audio stream, and hotkey listener."""
    global _model, _icon
    hide_console()
    _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    _icon = pystray.Icon(
        "ditado",
        create_icon(False),
        "Ditado - Speech-to-Text",
        create_menu(),
    )
    stream = sd.InputStream(samplerate=16000, channels=1, callback=audio_callback)
    stream.start()
    t = threading.Thread(target=hotkey_listener, daemon=True)
    t.start()
    _icon.run()


if __name__ == "__main__":
    main()
