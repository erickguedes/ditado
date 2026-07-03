import subprocess

import numpy as np

SAMPLE_RATE = 48000
CHANNELS = 2
BITRATE = "128k"


class MP3StreamEncoder:
    """Encodes PCM audio to MP3 via ffmpeg pipe (streaming)."""

    def __init__(self, output_path: str):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        self._process = subprocess.Popen(
            [
                "ffmpeg", "-y",
                "-f", "s16le",
                "-ar", str(SAMPLE_RATE),
                "-ac", str(CHANNELS),
                "-i", "pipe:0",
                "-codec:a", "libmp3lame",
                "-b:a", BITRATE,
                output_path,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            startupinfo=startupinfo,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self._closed = False

    def write(self, pcm_data: bytes):
        if not self._closed and pcm_data:
            self._process.stdin.write(pcm_data)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._process.stdin.close()
            self._process.wait(timeout=10)
        except Exception:
            self._process.kill()
            self._process.wait()

    def __del__(self):
        self.close()


def mix_to_stereo(mic_data: bytes | None, loop_data: bytes | None) -> bytes | None:
    """Mix mic (mono int16) and loopback (stereo int16) into stereo int16.

    L = microphone, R = loopback (left channel).
    If one stream is missing, the other fills its side; silence on the missing side.
    """
    if mic_data is None and loop_data is None:
        return None

    if mic_data is None:
        loop_np = np.frombuffer(loop_data, dtype=np.int16).reshape(-1, 2)
        out = np.zeros((len(loop_np), 2), dtype=np.int16)
        out[:, 1] = loop_np[:, 0]
        return out.tobytes()

    if loop_data is None:
        mic_np = np.frombuffer(mic_data, dtype=np.int16).reshape(-1, 1)
        out = np.zeros((len(mic_np), 2), dtype=np.int16)
        out[:, 0] = mic_np.flatten()
        return out.tobytes()

    mic_np = np.frombuffer(mic_data, dtype=np.int16).reshape(-1, 1)
    loop_np = np.frombuffer(loop_data, dtype=np.int16).reshape(-1, 2)

    min_frames = min(len(mic_np), len(loop_np))
    if min_frames == 0:
        return None

    out = np.zeros((min_frames, 2), dtype=np.int16)
    out[:, 0] = mic_np[:min_frames, 0]
    out[:, 1] = loop_np[:min_frames, 0]

    return out.tobytes()
