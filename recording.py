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
        self._loopback_rate = SAMPLE_RATE
        self._loopback_channels = 2

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
            blocksize=1024,
            callback=self._mic_callback,
        )
        self._mic_stream.start()

        if loopback_dev is not None:
            self._loopback_rate = int(loopback_dev["defaultSampleRate"])
            self._loopback_channels = min(loopback_dev["maxInputChannels"], 2)
            self._loopback_stream = self._py_audio.open(
                format=pyaudio.paInt16,
                channels=self._loopback_channels,
                rate=self._loopback_rate,
                input=True,
                input_device_index=loopback_dev["index"],
                frames_per_buffer=1024,
                stream_callback=self._loopback_callback,
            )
            self._loopback_stream.start_stream()

        self.state = self.STATE_RECORDING
        self._start_time = time.time()
        if self._on_state_change:
            self._on_state_change(self.state)

        self._stop_event.clear()
        self._mixer_thread = threading.Thread(target=self._mixer_loop, daemon=True)
        self._mixer_thread.start()

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
        return (None, pyaudio.paContinue)

    @staticmethod
    def _resample_pcm(data: bytes, src_rate: int, dst_rate: int, channels: int) -> bytes:
        """Resample PCM int16 from src_rate to dst_rate via linear interpolation."""
        if src_rate == dst_rate or not data:
            return data
        old = np.frombuffer(data, dtype=np.int16).reshape(-1, channels)
        src_frames = len(old)
        dst_frames = max(1, int(src_frames * dst_rate / src_rate))
        x_old = np.arange(src_frames, dtype=np.float64)
        x_new = np.linspace(0, src_frames - 1, dst_frames)
        out = np.zeros((dst_frames, channels), dtype=np.int16)
        for ch in range(channels):
            out[:, ch] = np.interp(x_new, x_old, old[:, ch].astype(np.float64)).astype(np.int16)
        return out.tobytes()

    def _mixer_loop(self):
        from encoder import mix_to_stereo

        LOOP_FRAME_BYTES = 1024 * 2 * 2  # 1024 stereo frames × int16 × 2ch
        loop_buf = b""

        while not self._stop_event.is_set() or not (
            self._mic_queue.empty() and self._loopback_queue.empty()
        ):
            try:
                mic_chunk = self._mic_queue.get_nowait()
            except queue.Empty:
                mic_chunk = None

            # Drain loopback queue, resample each chunk to SAMPLE_RATE
            while True:
                try:
                    raw = self._loopback_queue.get_nowait()
                    loop_buf += self._resample_pcm(
                        raw, self._loopback_rate, SAMPLE_RATE, self._loopback_channels
                    )
                except queue.Empty:
                    break

            if mic_chunk is None:
                if not self._stop_event.is_set():
                    time.sleep(0.01)
                continue

            # Consume exactly 1024 stereo frames of resampled loopback
            if len(loop_buf) >= LOOP_FRAME_BYTES:
                loop_chunk = loop_buf[:LOOP_FRAME_BYTES]
                loop_buf = loop_buf[LOOP_FRAME_BYTES:]
            else:
                loop_chunk = None

            pcm = mix_to_stereo(mic_chunk, loop_chunk)
            if pcm and self._encoder:
                self._encoder.write(pcm)
