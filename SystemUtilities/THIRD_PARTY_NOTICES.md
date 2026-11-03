# Third-party notices

Sekar's System Utilities' own code is MIT-licensed (see [LICENSE](LICENSE)). It uses the open-source packages and
downloadable models below, each under its own licence. Versions are the ones in `requirements.txt` /
`requirements-voice.txt`.

## Python packages included in releases

| Package | Version | Licence | Used for |
|---|---|---|---|
| [pywebview](https://github.com/r0x0r/pywebview) | 6.2.1 | BSD-3-Clause | The app window |
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | 2.3.0 | Apache-2.0 | Optional Claude API support |
| [pypdf](https://github.com/py-pdf/pypdf) | 6.21.2 | BSD-3-Clause | Reading short excerpts of PDFs for deep analysis |
| [pystray](https://github.com/moses-palmer/pystray) | 0.19.5 | LGPL-3.0 | The notification-area (tray) icon |
| [Pillow](https://github.com/python-pillow/Pillow) | 13.0.0 | MIT-CMU (HPND) | The tray icon image |

## Optional voice packages (`requirements-voice.txt`)

| Package | Version | Licence | Used for |
|---|---|---|---|
| [NumPy](https://numpy.org) | 2.5.4 | BSD-3-Clause (and bundled permissive licences) | Audio processing |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) | 0.5.6 | MIT | Microphone and bell |
| [openWakeWord](https://github.com/dscripka/openWakeWord) | 0.6.0 | Apache-2.0 (code) | "Hey Jarvis" wake word |
| [onnxruntime](https://github.com/microsoft/onnxruntime) | (installed with openWakeWord) | MIT | Runs the wake-word model |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | 1.2.1 | MIT | Local speech-to-text |
| [CTranslate2](https://github.com/OpenNMT/CTranslate2) | (installed with faster-whisper) | MIT | Runs Whisper |

### Not included: Piper

[Piper](https://github.com/OHF-Voice/piper1-gpl) (`piper-tts`), the natural-sounding voice for spoken replies, is
licensed **GPL-3.0-or-later**. To keep Sekar's System Utilities MIT-licensed, Piper is **not bundled** in releases or this
repository. If you install it yourself (`pip install piper-tts`), Sekar's System Utilities uses it automatically; otherwise
it speaks with the built-in Windows voice.

## Models downloaded on first use (never shipped)

These are fetched from their publishers the first time the feature is used, and stored on your PC. They are not
part of the installer or this repository.

| Model | Licence | Notes |
|---|---|---|
| openWakeWord pre-trained "hey_jarvis" model | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) | Non-commercial use only. © David Scripka, [openWakeWord](https://github.com/dscripka/openWakeWord). Sekar's System Utilities is free and non-commercial; a paid version would need its own wake-word model. |
| Whisper speech models (faster-whisper conversions, e.g. `large-v3-turbo`, `small.en`) | MIT | © OpenAI; converted by SYSTRAN. Used only when you choose local speech-to-text. |
| Piper voice `en_US-libritts_r-medium` (default, only if Piper is installed) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Trained on the LibriTTS-R dataset ([OpenSLR 141](http://www.openslr.org/141/)). Voice from [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices). |

Some other Piper voices have restrictive licences: for example `en_US-lessac` is trained on a research-only dataset,
and `hfc_female` / `hfc_male` are non-commercial. Check a voice's `MODEL_CARD` before using or sharing it.

## Online services (optional, your own account)

If you turn on an AI provider or cloud speech-to-text, Sekar's System Utilities sends requests to that service with **your
own API key** under **your own agreement** with them: Ollama (local, nothing leaves your PC), OpenAI-compatible
services (OpenAI, Google Gemini, Groq…), or Anthropic. No key or account is included with the app.

## Trademarks

Windows, Microsoft Defender and Windows Update are trademarks of Microsoft. NVIDIA, Intel, AMD, MSI, Realtek and
other names mentioned in the app are trademarks of their owners. Sekar's System Utilities is not affiliated with or endorsed
by any of them.
