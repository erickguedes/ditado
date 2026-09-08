"""Ditado — Windows speech-to-text dictation app.

F8: Press to record, press again to transcribe and paste
     the result into the active window via simulated Ctrl+V.
F9: Press to start/stop audio recording (microphone + system audio).
     Saves MP3 to ~/Music/Ditado/.
"""

import ctypes
import logging
import os
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import wave
from ctypes import wintypes
from datetime import datetime

import numpy as np
import pyperclip
import pystray
import sounddevice as sd
from faster_whisper import WhisperModel
from PIL import Image, ImageDraw

from recording import AudioRecorder

user32 = ctypes.windll.user32

WM_HOTKEY = 0x0312
VK_F8 = 0x77
VK_F9 = 0x78
MOD_NOREPEAT = 0x4000
HOTKEY_F8_ID = 1
HOTKEY_F9_ID = 2

MODEL_SIZE = "small"

LOG_PATH = os.path.expanduser(r"~\Music\Ditado\ditado.log")
VAD_THRESHOLD = 0.01
VAD_FRAME_MS = 30
VAD_PADDING_MS = 200
CHUNK_MAX_S = 120

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
_audio_recorder = None
_icon = None
_model = None
_hotkey_thread_running = True
_audio_stream = None


def hide_console():
    """Detach the console so the app runs silently in the background."""
    try:
        ctypes.windll.kernel32.FreeConsole()
    except Exception:
        pass


def setup_logging():
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    logging.basicConfig(
        filename=LOG_PATH,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        force=True,
    )


def _notify_error(msg: str):
    logging.error(msg)
    if _icon:
        try:
            _icon.notify(f"Error: {msg[:100]}", "Ditado")
        except Exception:
            pass


def _notify_info(msg: str):
    logging.info(msg)
    if _icon:
        try:
            _icon.notify(msg[:100], "Ditado")
        except Exception:
            pass


def create_icon(state: str = "idle"):
    """Render a 64x64 microphone icon.
    state: 'recording'=red, 'processing'=yellow, 'idle'=grey.
    """
    colors = {"recording": (220, 50, 50), "processing": (220, 180, 40), "idle": (140, 140, 140)}
    color = colors.get(state, colors["idle"])
    size = (64, 64)
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
    if status:
        pass  # overflow/underflow happen occasionally, not fatal
    if _recording:
        _audio_chunks.append(indata.copy())


def transcribe():
    """Transcribe accumulated audio, copy to clipboard, and simulate Ctrl+V paste."""
    global _recording, _audio_chunks
    if not _audio_chunks:
        if _icon:
            _icon.notify("No audio captured. Check your microphone.", "Ditado")
        return
    audio = np.concatenate(_audio_chunks, axis=0)
    _audio_chunks = []
    if np.max(np.abs(audio)) < 0.001:
        if _icon:
            _icon.notify("Audio too quiet. Check microphone volume.", "Ditado")
        return
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
            time.sleep(0.15)
            user32.keybd_event(0x11, 0, 0, 0)
            user32.keybd_event(0x56, 0, 0, 0)
            time.sleep(0.05)
            user32.keybd_event(0x56, 0, 2, 0)
            user32.keybd_event(0x11, 0, 2, 0)
            if _icon:
                preview = text[:60] + ("..." if len(text) > 60 else "")
                _icon.notify(f'Pasted: "{preview}"', "Ditado")
        else:
            if _icon:
                _icon.notify("No speech detected in recording.", "Ditado")
    except Exception as e:
        if _icon:
            _icon.notify(f"Transcription error: {e}", "Ditado")
    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass


def start_recording():
    """Begin audio capture and update the tray icon to red."""
    global _recording, _audio_chunks, _audio_recorder
    if _audio_recorder and _audio_recorder.is_recording:
        if _icon:
            _icon.notify("Stop audio recording (F9) first", "Ditado")
        return
    if _audio_stream and not _audio_stream.active:
        if _icon:
            _icon.notify("Audio stream lost. Restart Ditado.", "Ditado")
        return
    _audio_chunks = []
    _recording = True
    if _icon:
        _icon.icon = create_icon("recording")
        _icon.notify("Recording... Press F8 to stop", "Ditado")


def stop_recording():
    """Stop audio capture and launch transcription in a daemon thread."""
    global _recording
    _recording = False
    if _icon:
        _icon.icon = create_icon("processing")
        _icon.notify("Processing audio (may take a minute for longer recordings)...", "Ditado")
    threading.Thread(target=transcribe, daemon=True).start()


def toggle_recording():
    """Start or stop recording based on current state."""
    if _recording:
        stop_recording()
    else:
        start_recording()


def on_audio_recorder_state(new_state):
    """Called when AudioRecorder state changes."""
    if _icon:
        if new_state == AudioRecorder.STATE_RECORDING:
            _icon.icon = create_icon("recording")
            _icon.notify("Recording started", "Ditado")
        elif new_state == AudioRecorder.STATE_IDLE:
            _icon.icon = create_icon("processing")


def _decode_audio(path: str, sr: int = 16000, channels: int = 2):
    """Decode audio to float32 numpy array at target sample rate.
    Returns (N, C) array or (None, sr) on failure.
    """
    cmd = [
        "ffmpeg", "-i", path,
        "-f", "s16le", "-ac", str(channels), "-ar", str(sr),
        "-hide_banner", "-loglevel", "error",
        "pipe:1",
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        if r.returncode != 0:
            logging.error("ffmpeg decode failed: %s", r.stderr.decode(errors="replace")[:200])
            return None, sr
        raw = np.frombuffer(r.stdout, dtype=np.int16)
        if raw.size == 0:
            logging.warning("ffmpeg returned empty audio from %s", path)
            return None, sr
        audio = raw.astype(np.float32) / 32768.0
        return audio.reshape(-1, channels), sr
    except subprocess.TimeoutExpired:
        logging.error("ffmpeg decode timed out on %s", path)
        return None, sr
    except Exception as e:
        logging.error("ffmpeg decode error: %s", e)
        return None, sr


def _vad_filter(audio: np.ndarray, sr: int) -> np.ndarray:
    """Remove silence using frame-energy VAD (Meetily-inspired).
    Keeps speech segments with padding, concatenates them.
    """
    frame_len = int(sr * VAD_FRAME_MS / 1000)
    padding = int(sr * VAD_PADDING_MS / 1000)
    if len(audio.shape) > 1:
        mono = np.mean(audio, axis=1)
    else:
        mono = audio

    rms = np.array([
        np.sqrt(np.mean(mono[i:i+frame_len]**2))
        for i in range(0, len(mono), frame_len)
    ])
    is_speech = rms > VAD_THRESHOLD
    if not np.any(is_speech):
        return audio

    speech_idx = np.where(is_speech)[0]
    pad_frames = padding // frame_len

    gap = speech_idx[1:] - speech_idx[:-1]
    breaks = np.where(gap > pad_frames * 2)[0]
    segments = []
    seg_start = max(0, speech_idx[0] - pad_frames)
    for b in breaks:
        seg_end = min(len(is_speech), speech_idx[b] + pad_frames)
        segments.append((seg_start * frame_len, min(seg_end * frame_len + frame_len, len(audio))))
        seg_start = max(0, speech_idx[b + 1] - pad_frames)
    seg_end = min(len(is_speech), speech_idx[-1] + pad_frames)
    segments.append((seg_start * frame_len, min(seg_end * frame_len + frame_len, len(audio))))

    filtered = np.concatenate([audio[s:e] for s, e in segments])
    kept = len(filtered) / len(audio) * 100 if len(audio) > 0 else 0
    logging.info("VAD: kept %.1f%% of audio (%d -> %d samples)", kept, len(audio), len(filtered))
    return filtered


def _segment_rms(audio: np.ndarray, sr: int, start: float, end: float, channel: int) -> float:
    """RMS energy of a segment in a given stereo channel."""
    lo = max(0, int(start * sr))
    hi = min(audio.shape[0], int(end * sr))
    if hi - lo < 64:
        return 0.0
    chunk = audio[lo:hi, channel]
    return float(np.sqrt(np.mean(chunk ** 2)))


def _diarize_segments(segments, audio: np.ndarray, sr: int):
    """Label each segment as 'Me' (mic/L) or 'Other' (loopback/R) via channel energy."""
    labels = []
    for seg in segments:
        e_l = _segment_rms(audio, sr, seg.start, seg.end, 0)
        e_r = _segment_rms(audio, sr, seg.start, seg.end, 1)
        if max(e_l, e_r) < 0.005:
            labels.append(None)
        elif e_l > e_r * 1.5:
            labels.append("Me")
        elif e_r > e_l * 1.5:
            labels.append("Other")
        else:
            labels.append(None)
    prev = "Me"
    for i in range(len(labels)):
        if labels[i] is None:
            labels[i] = prev
        else:
            prev = labels[i]
    return labels


def _format_timestamp(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m:02d}:{s:02d}"


def _check_audio_file(path: str) -> bool:
    """Validate audio file has content before attempting transcription."""
    if not os.path.exists(path):
        _notify_error(f"Audio file not found: {path}")
        return False
    size = os.path.getsize(path)
    if size < 1024:
        _notify_error(f"Audio file too small ({size}B): {path}")
        return False
    audio, sr = _decode_audio(path, channels=2)
    if audio is None or len(audio) < sr:
        _notify_error(f"Audio too short or corrupt: {path}")
        return False
    rms_per_ch = [np.sqrt(np.mean(audio[:, c]**2)) for c in range(audio.shape[1])]
    if max(rms_per_ch) < VAD_THRESHOLD:
        _notify_error("Audio is all silence — nothing to transcribe")
        return False
    return True


def _transcribe_chunked(wav_path: str, lang: str | None) -> list:
    """Transcribe long audio in chunks to avoid OOM (Meetily-inspired chunking)."""
    audio, sr = _decode_audio(wav_path, channels=1)
    if audio is None:
        return []

    total_samples = len(audio)
    chunk_samples = CHUNK_MAX_S * sr
    all_segments = []
    offset = 0.0

    for start in range(0, total_samples, chunk_samples):
        end = min(start + chunk_samples, total_samples)
        chunk = audio[start:end]

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            chunk_path = tmp.name
        try:
            with wave.open(chunk_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                chunk_int16 = (chunk * 32767).astype(np.int16)
                wf.writeframes(chunk_int16.tobytes())

            segments, _ = _model.transcribe(chunk_path, language=lang, beam_size=5)
            for seg in segments:
                seg.start += offset
                seg.end += offset
                all_segments.append(seg)
        finally:
            try:
                os.unlink(chunk_path)
            except Exception:
                pass
        offset += len(chunk) / sr
        logging.info("Transcribed chunk %d/%d (%.1fs)", start // chunk_samples + 1,
                     (total_samples + chunk_samples - 1) // chunk_samples, offset)

    return all_segments


def transcribe_file(mp3_path: str, duration: float):
    """Transcribe MP3, diarize speakers via channel energy, save .txt.
    Uses VAD (silence removal) + chunking for long audio (Meetily-inspired).
    """
    txt_path = os.path.splitext(mp3_path)[0] + ".txt"
    logging.info("Transcribing %s (duration=%.1fs)", mp3_path, duration)

    # Validate audio
    if not _check_audio_file(mp3_path):
        return

    try:
        # Decode + apply VAD
        audio_stereo, sr = _decode_audio(mp3_path, channels=2)
        if audio_stereo is None:
            _notify_error("Failed to decode audio")
            return

        audio_vad = _vad_filter(audio_stereo, sr)

        # Write filtered audio to temp WAV
        mono = np.mean(audio_vad, axis=1)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            wav_path = tmp.name
        try:
            with wave.open(wav_path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(sr)
                mono_int16 = (mono * 32767).astype(np.int16)
                wf.writeframes(mono_int16.tobytes())
        except Exception as e:
            _notify_error(f"Failed to write temp WAV: {e}")
            try:
                os.unlink(wav_path)
            except Exception:
                pass
            return

        # Transcribe (chunked if long)
        lang = _language if _language else None
        try:
            if duration > CHUNK_MAX_S:
                logging.info("Audio long (%.0fs), using chunked transcription", duration)
                segments = _transcribe_chunked(wav_path, lang)
            else:
                segments_gen, info = _model.transcribe(wav_path, language=lang, beam_size=5)
                segments = list(segments_gen)
        finally:
            try:
                os.unlink(wav_path)
            except Exception:
                pass

        if not segments:
            _notify_error("Transcription returned no segments — audio may be silence or unrecognized")
            return

        # Diarization using original stereo (before VAD) for speaker energy comparison
        speakers = _diarize_segments(segments, audio_stereo, sr)

        lines: list[str] = []
        lines.append("=== Diarized Transcription ===")
        mins, secs = divmod(int(duration), 60)
        lines.append(f"Duration: {mins}m{secs}s | Segments: {len(segments)}")
        lines.append("")

        speaker_stats: dict[str, float] = {}
        for seg, spk in zip(segments, speakers):
            ts = f"[{_format_timestamp(seg.start)} - {_format_timestamp(seg.end)}]"
            text = seg.text.strip()
            lines.append(f"{ts} {spk}: {text}")
            speaker_stats[spk] = speaker_stats.get(spk, 0) + (seg.end - seg.start)

        lines.append("")
        lines.append("--- Speaker Statistics ---")
        total = duration
        for spk, dur in sorted(speaker_stats.items()):
            pct = dur / total * 100 if total > 0 else 0
            lines.append(f"{spk}: {_format_timestamp(dur)} ({pct:.0f}%)")

        output = "\n".join(lines)
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(output)

        logging.info("Transcription saved to %s (%d segments, %d speakers)",
                     txt_path, len(segments), len(speaker_stats))

        if _icon:
            _icon.icon = create_icon("idle")
            preview = segments[0].text[:80] + ("..." if len(segments[0].text) > 80 else "")
            _icon.notify(
                f"Transcribed ({mins}m{secs}s) - {len(speaker_stats)} speaker(s)\n{preview}",
                "Ditado",
            )

    except Exception as e:
        logging.error("Transcription failed: %s\n%s", e, traceback.format_exc())
        _notify_error(f"Transcription failed: {e}")

    finally:
        if _icon:
            _icon.icon = create_icon("idle")


def toggle_audio_recording():
    """Start or stop audio recording (F9) based on current state."""
    global _audio_recorder
    if _recording:
        _notify_info("Stop dictation (F8) first")
        return
    if _audio_recorder and _audio_recorder.is_recording:
        result = _audio_recorder.stop()
        _audio_recorder = None
        if result:
            path, duration = result
            mins, secs = divmod(int(duration), 60)
            size = os.path.getsize(path) / (1024 * 1024)
            logging.info("Recording saved: %s (%.0fs, %.1fMB)", path, duration, size)
            _notify_info(f"Recording saved - Transcribing... ({mins}m{secs}s / {size:.1f}MB)")
            t = threading.Thread(target=transcribe_file, args=(path, duration))
            t.daemon = False
            t.start()
    else:
        recorder = AudioRecorder(on_state_change=on_audio_recorder_state)
        recorder.start()
        if recorder.is_recording:
            _audio_recorder = recorder
            logging.info("F9 recording started")


def show_about():
    """Show a Windows message box with app info."""
    ctypes.windll.user32.MessageBoxW(
        0,
        "Ditado v1.2.1\n\n"
        "Offline dictation & meeting recording for Windows.\n"
        "100% local speech recognition using faster-whisper.\n\n"
        "Created by Erick Guedes\n"
        "https://github.com/erickguedes/ditado\n\n"
        "MIT License \u00a9 2026",
        "About Ditado",
        0,
    )


def open_recordings_folder():
    """Open the recordings folder in File Explorer."""
    path = os.path.expanduser(r"~\Music\Ditado")
    os.makedirs(path, exist_ok=True)
    os.startfile(path)


def hotkey_listener():
    """Run a Win32 message pump in a daemon thread to detect F8 and F9 hotkey presses."""
    global _hotkey_thread_running
    user32.RegisterHotKey(None, HOTKEY_F8_ID, MOD_NOREPEAT, VK_F8)
    user32.RegisterHotKey(None, HOTKEY_F9_ID, MOD_NOREPEAT, VK_F9)
    msg = wintypes.MSG()
    while _hotkey_thread_running:
        ret = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
        if ret == 0:
            break
        if msg.message == WM_HOTKEY:
            if msg.wParam == HOTKEY_F8_ID:
                toggle_recording()
            elif msg.wParam == HOTKEY_F9_ID:
                toggle_audio_recording()
    user32.UnregisterHotKey(None, HOTKEY_F8_ID)
    user32.UnregisterHotKey(None, HOTKEY_F9_ID)


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
    recording_f9 = _audio_recorder and _audio_recorder.is_recording
    return pystray.Menu(
        pystray.MenuItem(
            lambda item: "⏹ Stop Recording" if _recording else "🎤 Start Recording",
            toggle_recording,
            default=True,
        ),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(
            lambda item: "⏹ Stop Audio Recording" if recording_f9 else "🔴 Start Audio Recording (F9)",
            toggle_audio_recording,
        ),
        pystray.MenuItem(
            "Open Recordings Folder",
            open_recordings_folder,
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
        pystray.MenuItem("About Ditado", show_about),
        pystray.MenuItem("Quit", quit_app),
    )


def quit_app():
    """Cleanly shut down the hotkey thread, systray icon, and process."""
    global _hotkey_thread_running, _audio_recorder
    if _audio_recorder and _audio_recorder.is_recording:
        _audio_recorder.cleanup()
        _audio_recorder = None
    _hotkey_thread_running = False
    if _icon:
        _icon.stop()
    os._exit(0)


def main():
    """Initialize model, systray icon, audio stream, and hotkey listener."""
    global _model, _icon, _audio_stream
    hide_console()
    setup_logging()
    logging.info("Ditado v1.2.0 starting...")
    _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    logging.info("Model loaded: %s (CPU int8)", MODEL_SIZE)
    _icon = pystray.Icon(
        "ditado",
        create_icon("idle"),
        "Ditado - Speech-to-Text",
        create_menu(),
    )
    _audio_stream = sd.InputStream(samplerate=16000, channels=1, callback=audio_callback)
    _audio_stream.start()
    t = threading.Thread(target=hotkey_listener, daemon=True)
    t.start()
    logging.info("Hotkey listener started (F8=dictation, F9=meeting)")
    _icon.run()
    logging.info("Ditado shutting down")


if __name__ == "__main__":
    main()
