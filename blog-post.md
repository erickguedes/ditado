Building Ditado: An Offline Speech-to-Text App for Windows (and Why I Added Meeting Recording)
June 24, 2026
I spend a large part of my day talking to AI.

Whether I'm brainstorming ideas, writing documentation, answering emails, or taking notes in Notion and Obsidian, speaking is simply faster than typing. My thoughts move faster than my fingers ever could.

The problem is that most dictation software asks you to make a compromise.

Some require a monthly subscription. Others send every recording to the cloud. Some have excellent English support but perform noticeably worse in Portuguese. None of them felt like a tool I wanted to keep open all day.

So I built my own.

Ditado is an offline-first dictation application for Windows that turns speech into text locally using Whisper, then automatically pastes the transcription into whatever application you're using. No accounts. No API keys. No cloud processing. Just press F8, speak naturally, and continue working.

After using it every day, however, I realized another workflow deserved the same treatment.

I also wanted a simple way to record meetings.

Not just my own microphone, but both sides of the conversation—Teams calls, Zoom meetings, interviews, voice chats—without installing another application or relying on cloud services.

That became the new F9 Audio Recording mode.

Dictation (F8)
The original workflow is intentionally simple.

Press F8 to begin recording.

Speak naturally.

Press F8 again.

The audio is transcribed locally using faster-whisper, and the resulting text is automatically pasted into the active application using a simulated Ctrl+V.

Because everything runs locally, your audio never leaves your computer.

There are no accounts to create, no subscription to maintain, and no latency waiting for a remote server.

The application lives quietly in the Windows system tray and is always available through a global hotkey.

Audio Recording (F9)
After relying on Ditado daily, I found myself repeatedly opening a second application whenever I needed to record a meeting.

That felt unnecessary.

The solution was adding a second recording mode that captures both audio sources simultaneously:

your microphone
your computer's system audio
Press F9 once to begin recording.

Press F9 again to finish.

The recording is saved as an MP3 and automatically transcribed into a .txt file with speaker labels.

~/Music/Ditado/
Rather than mixing everything together, Ditado stores the recording in stereo:

Left channel: microphone
Right channel: system audio
This channel separation is what makes speaker identification possible. After transcription, each segment is compared across both channels: the dominant energy tells us who spoke. Microphone dominant means "Me." System audio dominant means "Other."

No GPU required. No cloud calls. Just numpy and a simple energy comparison.

Design Decisions
Everything stays offline
Privacy wasn't an optional feature—it was the entire motivation behind the project.

Speech recordings often contain personal information, company discussions, passwords, customer conversations, or unfinished ideas.

With Ditado, nothing is uploaded.

Speech recognition runs locally using faster-whisper, while audio recording is written directly to disk.

If your computer is offline, Ditado still works exactly the same.

WASAPI Loopback
Recording your own microphone is easy.

Recording exactly what your computer is playing is surprisingly harder.

Windows exposes this functionality through WASAPI Loopback, which captures the audio you hear without requiring virtual audio cables or third-party drivers.

Unfortunately, Python's audio ecosystem on Windows is fragmented.

The library I already used for dictation doesn't expose loopback devices, so recording meetings required introducing a second audio backend dedicated to system audio capture.

Once both streams are available, they can be synchronized and recorded together.

Separate channels instead of mixing everything
Many recording applications simply mix every source into mono.

That's simpler.

It's also irreversible.

Once two voices are merged together, separating them later becomes significantly more difficult.

Ditado instead stores:

Left = microphone
Right = system audio

This paid off immediately. The stereo recording enables a straightforward channel-energy diarization: for each transcribed segment, compare RMS energy in the left channel versus the right channel. Whichever side is louder gets the label.

It is not perfect—overlapping speech, loud environments, and single-speaker calls still challenge the approach. But for two-person conversations on a call, it works well enough to tell who said what.

Streaming MP3 encoding
Meetings can easily last an hour or more.

Keeping raw audio in memory until recording finishes would consume an unnecessary amount of RAM.

Instead, Ditado streams audio directly into ffmpeg, which continuously encodes the MP3 while recording is still in progress.

Memory usage stays essentially constant regardless of recording length.

Two independent workflows
Although both features use the microphone, dictation and meeting recording solve different problems.

Running them simultaneously would create ambiguous behavior.

Which recording owns the microphone?

Which feature should control the tray icon?

Which recording stops first?

Rather than introducing unnecessary complexity, Ditado simply keeps the two modes mutually exclusive.

If one is active, the other waits.

The result is a predictable user experience and considerably simpler internal state management.

Technical Highlights
Fully offline speech recognition using faster-whisper
Global F8 hotkey for instant dictation
Global F9 hotkey for meeting recording
13 supported languages plus automatic language detection (auto-detect working for Portuguese, English, Spanish, and more)
Automatic transcription of every F9 recording to .txt with speaker labels (Me / Other)
Channel-energy based diarization using stereo separation (no GPU required)
F9 reliability fixes: sample rate resampling, silent period correction, terminal window suppression, streaming blocksize sync
Windows system tray application
Automatic paste into any text field
Microphone + system audio recording
Stereo MP3 (microphone left, system audio right)
Streaming MP3 encoding through ffmpeg
Graceful shutdown that safely finalizes recordings before exit
Startup integration through the tray menu
Challenges
The transcription side of the project turned out to be relatively straightforward.

Reliable audio capture was not.

Supporting both live dictation and meeting recording meant combining different Windows audio APIs, coordinating multiple recording threads, synchronizing two independent audio sources, and ensuring recordings always finish cleanly—even if the application is closed while recording.

Adding F9 also meant rethinking the application's internal state.

Originally there was only one recording mode.

Introducing a second required separating responsibilities so that dictation could remain untouched while the new recording pipeline operated independently.

The goal throughout the refactor was simple:

Existing users shouldn't notice that anything changed.

They simply gained another capability.

The F9 mode itself had bugs that only appeared in real-world use. The microphone and loopback devices often run at different sample rates (48000 Hz vs 44100 or 96000 Hz), which produced slowed, distorted audio. A silent period at the start of recordings caused the MP3 encoder to miss the first few seconds. The Windows terminal window flashed briefly when ffmpeg started. And an 18-second cap turned out to be caused by the loopback callback aborting prematurely, starving the encoder pipeline.

Each issue was small on its own, but together they made the feature unreliable. Debugging them required understanding how Windows audio, Python threads, and ffmpeg pipes interact—a combination that is surprisingly hard to test systematically.

Speaker diarization also proved trickier than expected. My first attempt used spectral centroid analysis—essentially detecting pitch differences—to cluster speakers. It works well in theory but fails on phone calls, where audio compression and narrow bandwidth make voices sound spectrally similar. I scrapped that approach and switched to channel-energy comparison, which uses the stereo separation already built into the recording format. Simpler, more reliable, and zero GPU dependency.

What's Next
The current version (v1.2.0) already solves the problems that motivated the project.

I use Ditado every day to interact with AI, write documentation, capture ideas, record meetings, and get diarized transcripts back.

Automatic transcription and speaker identification are no longer future plans—they work today.

What comes next is refinement. The channel-energy diarization handles two-person conversations well, but it is limited to "Me" and "Other." Multi-speaker scenarios (three or more people in a room) would benefit from MFCC-based features or, eventually, a lightweight neural diarization model that runs on CPU. Multi-language recordings could be improved by per-segment language detection instead of a single global setting.

The long-term vision is a complete meeting analysis pipeline: talk-time ratios, silence detection, topic extraction, and searchable transcripts. But the foundation is solid, and it all stays 100% local and open source.

Why Open Source?
Ditado is released under the MIT License because I believe privacy tools become more trustworthy when people can inspect how they work.

If you're learning Python, experimenting with Whisper, or building desktop applications for Windows, I hope parts of this project are useful.

And if you're simply looking for a free, offline dictation tool that works well for Portuguese—and supports multiple languages—you can download it today and start speaking instead of typing.

Sometimes the best side projects are simply the ones you end up using every single day.

Built with: Python • faster-whisper • sounddevice • PyAudioWPatch • ffmpeg • PyInstaller • Inno Setup

GitHub: https://github.com/erickguedes/ditado

EG
Erick Guedes
