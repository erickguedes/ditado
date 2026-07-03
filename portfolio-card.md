ditado — Offline Dictation & Audio Recording
Offline-first Windows application for private AI dictation and meeting recording using local speech recognition. Supports 13 languages + auto-detect with zero cloud dependency.

Role
Creator

Year
2026

Stack
Python · faster-whisper · sounddevice · pyaudiowpatch · ffmpeg · PyInstaller

Context
Cloud-based speech recognition raises privacy concerns, requires internet connectivity, and performs inconsistently for Brazilian Portuguese. Professionals also need an easy way to capture and transcribe meetings locally without relying on third-party recording services.

Approach
Designed and built a desktop application that runs entirely offline from the Windows system tray.

F8 Dictation: record speech, transcribe locally with faster-whisper, and automatically paste the result into any application.

F9 Recording: capture microphone and system audio simultaneously via WASAPI loopback with stereo channel separation (L=microphone, R=system audio). Fixes applied for sample rate mismatch (resampling), silent period, terminal window, and 18-second cap.

Auto-transcription: each F9 recording is automatically transcribed to a .txt file with speaker labels ("Me" / "Other") derived from stereo channel energy — no GPU required.

Auto-detect language: supports 13 languages plus automatic detection, working for Portuguese, English, Spanish, and more.

Packaged as a standalone Windows installer using PyInstaller and Inno Setup. MIT licensed and fully open source.

Outcome
Production-ready Windows release (v1.2.0).
Near-human transcription quality for Brazilian Portuguese.
100% local processing with no cloud services.
Reliable multi-minute meeting capture with both sides of the conversation identified.
Enables private dictation and meeting transcription without subscriptions or internet access.
Repository →
