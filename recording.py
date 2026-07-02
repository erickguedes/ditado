import os
import queue
import threading
import time
from datetime import datetime

import numpy as np
import pyaudiowpatch as pyaudio
import sounddevice as sd

from encoder import MP3StreamEncoder

RECORDINGS_DIR = os.path.expanduser(r"~\Music\Ditado")
SAMPLE_RATE = 48000


class AudioRecorder:
    """Records microphone + system audio (WASAPI loopback) to MP3.

    State machine: IDLE -> RECORDING -> STOPPING -> IDLE.
    on_state_change callback receives the new state int.
    """

    STATE_IDLE = 0
    STATE_RECORDING = 1
    STATE_STOPPING = 2

    def __init__(self, on_state_change=None):
        self.state = self.STATE_IDLE
        self._on_state_change = on_state_change
        self._mic_queue = queue.Queue()
        self._loopback_queue = queue.Queue()
        self._encoder = None
        self._mic_stream = None
        self._loopback_stream = None
        self._mixer_thread = None
        self._stop_event = threading.Event()
        self._output_path = None
        self._py_audio = None
        self._start_time = 0.0
        self._has_loopback = False

    @property
    def is_recording(self):
        return self.state == self.STATE_RECORDING

    def start(self):
        if self.state != self.STATE_IDLE:
            return

        os.makedirs(RECORDINGS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H-%M-%S")
        self._output_path = os.path.join(RECORDINGS_DIR, f"{timestamp}.mp3")

        self._py_audio = pyaudio.PyAudio()
        self._has_loopback = False

        try:
            loopback_dev = self._py_audio.get_default_wasapi_loopback()
            self._has_loopback = True
        except (OSError, LookupError):
            loopback_dev = None

        self._encoder = MP3StreamEncoder(self._output_path)

        self._mic_stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            callback=self._mic_callback,
        )
        self._mic_stream.start()

        if loopback_dev is not None:
            loopback_rate = int(loopback_dev["defaultSampleRate"])
            loopback_channels = min(loopback_dev["maxInputChannels"], 2)
            self._loopback_stream = self._py_audio.open(
                format=pyaudio.paInt16,
                channels=loopback_channels,
                rate=loopback_rate,
                input=True,
                input_device_index=loopback_dev["index"],
                frames_per_buffer=1024,
                stream_callback=self._loopback_callback,
            )
            self._loopback_stream.start_stream()

        self._stop_event.clear()
        self._mixer_thread = threading.Thread(target=self._mixer_loop, daemon=True)
        self._mixer_thread.start()

        self.state = self.STATE_RECORDING
        self._start_time = time.time()
        if self._on_state_change:
            self._on_state_change(self.state)

    def stop(self):
        if self.state != self.STATE_RECORDING:
            return None

        self.state = self.STATE_STOPPING
        if self._on_state_change:
            self._on_state_change(self.state)

        if self._mic_stream:
            self._mic_stream.stop()
            self._mic_stream.close()
            self._mic_stream = None

        if self._loopback_stream:
            self._loopback_stream.stop_stream()
            self._loopback_stream.close()
            self._loopback_stream = None

        self._stop_event.set()

        if self._mixer_thread:
            self._mixer_thread.join(timeout=10)

        if self._encoder:
            self._encoder.close()
            self._encoder = None

        if self._py_audio:
            self._py_audio.terminate()
            self._py_audio = None

        duration = time.time() - self._start_time
        self._start_time = 0.0
        result = (self._output_path, duration)
        self._output_path = None

        self.state = self.STATE_IDLE
        if self._on_state_change:
            self._on_state_change(self.state)

        return result

    def cleanup(self):
        """Emergency cleanup when the app quits mid-recording."""
        self.state = self.STATE_STOPPING
        for stream in (self._mic_stream,):
            if stream:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
        for stream in (self._loopback_stream,):
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception:
                    pass
        self._mic_stream = None
        self._loopback_stream = None
        if self._py_audio:
            try:
                self._py_audio.terminate()
            except Exception:
                pass
            self._py_audio = None
        if self._encoder:
            try:
                self._encoder.close()
            except Exception:
                pass
            self._encoder = None
        self.state = self.STATE_IDLE

    def _mic_callback(self, indata, frames, time_info, status):
        if self.state == self.STATE_RECORDING:
            chunk = (indata * 32767).clip(-32768, 32767).astype(np.int16).tobytes()
            self._mic_queue.put_nowait(chunk)

    def _loopback_callback(self, in_data, frame_count, time_info, status):
        if self.state == self.STATE_RECORDING and in_data is not None:
            self._loopback_queue.put_nowait(in_data)

    def _mixer_loop(self):
        from encoder import mix_to_stereo

        while not self._stop_event.is_set() or not (
            self._mic_queue.empty() and self._loopback_queue.empty()
        ):
            mic_chunk = None
            loop_chunk = None
            try:
                mic_chunk = self._mic_queue.get(timeout=0.2)
            except queue.Empty:
                pass
            try:
                loop_chunk = self._loopback_queue.get(timeout=0.2)
            except queue.Empty:
                pass
            if mic_chunk is None and loop_chunk is None:
                continue
            pcm = mix_to_stereo(mic_chunk, loop_chunk)
            if pcm and self._encoder:
                self._encoder.write(pcm)
