# AGENTS.md — Ditado

## Identity

Dictation app for Windows — Portuguese speech-to-text with 13 languages + auto-detect. Uses faster-whisper locally. F8 hotkey to record and paste into any app.

## Commands

```bash
pip install faster-whisper sounddevice numpy pyperclip pystray pillow pyaudiowpatch
python ditado.py
```

Requires ffmpeg in PATH for MP3 encoding. F9 hotkey captures mic + system (WASAPI loopback) to MP3.

## Build

```bash
pip install pyinstaller
pyinstaller ditado.spec          # → dist/ditado.exe
python build.py --installer      # + Inno Setup installer (requires iscc.exe)
```

## Portfolio

```yaml
stack: Python
infra:
  tipo: local_only
  db: nenhum
  docker: false
  dominio: ""
mercado:
  problema: "Digitação lenta para capturar ideias"
  publico_alvo: "Profissionais que usam IA e tomam notas"
  proposta_valor: "Dictação offline com Whisper local"
  concorrencia: "Wispr Flow, Dictly"
  estagio: lancado
```
