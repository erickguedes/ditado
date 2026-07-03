"""Test AudioRecorder: verifica se duracao do MP3 corresponde ao tempo real."""

import os
import subprocess
import time

from recording import AudioRecorder


def get_mp3_duration(path):
    """Retorna duracao real em segundos via ffprobe."""
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", path],
        capture_output=True, text=True,
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    if r.returncode == 0 and r.stdout.strip():
        return float(r.stdout.strip())
    return None


def test(record_seconds, label):
    print(f"\n=== Teste: gravar {record_seconds}s ({label}) ===")
    t0 = time.time()
    recorder = AudioRecorder()
    t1 = time.time()
    print(f"  init AudioRecorder: {t1-t0:.1f}s")

    recorder.start()
    t2 = time.time()
    print(f"  start(): {t2-t1:.1f}s")
    print(f"  is_recording: {recorder.is_recording}")

    time.sleep(record_seconds)

    t3 = time.time()
    result = recorder.stop()
    t4 = time.time()
    print(f"  stop(): {t4-t3:.1f}s")

    if result is None:
        print("  ERRO: stop() retornou None")
        return None
    path, reported_dur = result
    actual_dur = get_mp3_duration(path)
    size_kb = os.path.getsize(path) / 1024

    print(f"  path: {path}")
    print(f"  reported_duration: {reported_dur:.1f}s")
    print(f"  mp3_duration (ffprobe): {actual_dur:.1f}s" if actual_dur else "  mp3_duration: ERROR")
    print(f"  file_size: {size_kb:.0f}KB")

    # Verificar que a duracao real do MP3 bate com o tempo de gravacao
    if actual_dur is not None:
        diff = abs(actual_dur - record_seconds)
        if diff < 3:
            print(f"  PASSOU: MP3 tem {actual_dur:.1f}s (gravado {record_seconds}s)")
        else:
            print(f"  FALHOU: MP3 tem {actual_dur:.1f}s, esperado ~{record_seconds}s")

    print(f"  Tamanho esperado p/ {record_seconds}s @128kbps: ~{record_seconds * 16:.0f}KB")
    return actual_dur


if __name__ == "__main__":
    # Teste curto (5s) e medio (15s)
    d1 = test(5, "curto")
    d2 = test(15, "medio")
    print("\n=== RESUMO ===")
    print(f"Teste 5s:  MP3={d1:.1f}s" if d1 else "Teste 5s:  FALHA")
    print(f"Teste 15s: MP3={d2:.1f}s" if d2 else "Teste 15s: FALHA")
