# PRD — Audio Recording Extension (F9)

## Overview

Extend **Ditado** with a lightweight audio recording feature designed for meetings, calls, interviews, and voice notes.

Unlike the existing **F8 Dictation** workflow (which records, transcribes, and pastes text), this feature focuses on **capturing high-quality audio** from both the microphone and the computer output, saving it locally as an MP3 file.

The implementation should remain **offline-first**, require **no cloud services**, and have **minimal CPU and memory usage**.

---

# Goals

- Record both sides of a conversation.
- Single hotkey to start/stop recording.
- Save recordings automatically.
- No configuration required.
- Work with any application (Google Meet, Teams, Zoom, Discord, browser, etc.).
- Remain lightweight and always available in the background.

---

# User Story

> As a user,
> I want to press a single hotkey before starting a meeting,
> so that everything I say and everything I hear is recorded into a single audio file that I can later transcribe, summarize, or archive.

---

# Hotkey

## F9

Behavior:

First press:

- starts recording

Second press:

- stops recording
- finalizes the MP3
- saves the file

The behavior mirrors the existing F8 toggle.

---

# Audio Sources

The recording should capture:

## Input

- Default Windows microphone

## Output

- Default Windows playback device
- Captured using WASAPI Loopback

The final recording must contain **both sources mixed together** into a single stereo or mono MP3.

The objective is to recreate exactly what the user experienced during the meeting.

---

# Output Format

Preferred:

- MP3
- 128 kbps CBR

Acceptable:

- 160 kbps
- 192 kbps

Avoid WAV as the default due to file size.

---

# Storage Location

Automatically save files to:

```
%USERPROFILE%\Music\Ditado\
```

Examples:

```
C:\Users\John\Music\Ditado\
```

```
C:\Users\Erick\Music\Ditado\
```

The folder should be created automatically if it does not exist.

---

# File Naming

Recommended format:

```
YYYY-MM-DD HH-mm-ss.mp3
```

Example:

```
2026-06-30 15-42-18.mp3
```

Alternative acceptable format:

```
meeting-2026-06-30-15-42-18.mp3
```

Names must be unique.

---

# Notifications

When recording starts:

```
Recording started
```

When recording finishes:

```
Recording saved

C:\Users\...\Music\Ditado\2026-06-30 15-42-18.mp3
```

---

# Tray Icon

While recording:

- tray icon becomes red (same behavior as Dictation)

When idle:

- normal microphone icon

No additional tray icons should be introduced.

---

# Tray Menu

Optional additions:

```
Start Audio Recording (F9)

Stop Audio Recording

Open Recordings Folder
```

---

# Recording Pipeline

```
Microphone
        \
         \
          ---> Mixer ----> MP3 Encoder ----> File
         /
Loopback
(System Audio)
```

The mixer should synchronize both streams before encoding.

---

# Technical Requirements

## Windows API

Preferred:

- WASAPI
- WASAPI Loopback

---

## Python Libraries

Preferred stack:

- soundcard
or
- PyAudioWPatch

Encoding:

- lameenc
or
- pydub + ffmpeg (less preferred)

Avoid heavy multimedia frameworks.

---

# Performance Targets

Memory:

- < 50 MB additional RAM

CPU:

- Near idle while recording
- No GPU usage

The recorder should comfortably run alongside meetings and the existing Dictado functionality.

---

# Error Handling

If no microphone is available:

```
No microphone detected.
```

If loopback cannot be initialized:

```
Unable to capture system audio.
```

If saving fails:

```
Recording could not be saved.
```

Recording should fail gracefully without affecting Dictado.

---

# Compatibility

Supported:

- Windows 10
- Windows 11

Audio devices:

- USB headsets
- Bluetooth headsets
- P2 headphones/headsets
- Built-in laptop speakers
- USB microphones

The solution should always use the current Windows default devices.

---

# Non-Goals (MVP)

The initial implementation does **not** include:

- Live transcription
- AI summarization
- Automatic meeting detection
- Silence detection
- Pause/resume
- Multi-track recording
- Cloud synchronization
- Video recording

---

# Future Enhancements

Possible future features:

- Automatic transcription after recording
- Generate meeting summary using an LLM
- Action item extraction
- Speaker diarization
- Automatic file naming based on calendar events
- Recording history window
- Search recordings
- Recording quality selection
- FLAC export
- Optional separate microphone/system tracks
- Automatic upload to Obsidian or Notion
- Configurable output directory

---

# Acceptance Criteria

- Pressing **F9** starts recording.
- Pressing **F9** again stops recording.
- The resulting file is an MP3.
- Both microphone and system audio are present (we will hear all meeting conversation or cold call talk).
- Files are saved automatically under the user's Music\Ditado folder.
- File names are timestamp-based and unique.
- Notifications are displayed on start and finish.
- CPU and memory usage remain low.
- The feature operates independently of the existing F8 Dictation workflow.