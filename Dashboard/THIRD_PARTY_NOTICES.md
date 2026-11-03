# Third-party notices

Sekar's Dashboard's own code is MIT-licensed (see [LICENSE](LICENSE)). It uses the open-source packages, downloadable
models and online services below, each under its own licence or terms. Nothing on this page is included in this
repository: you install the packages yourself with `pip`, and models are downloaded on first use.

## Python packages (`requirements.txt`)

| Package | Licence | Used for |
|---|---|---|
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause | The dashboard window |
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | Apache-2.0 | Optional Claude API support |
| [Pillow](https://github.com/python-pillow/Pillow) | MIT-CMU (HPND) | Photos and the tray icon |
| [pillow-heif](https://github.com/bigcat88/pillow_heif) | BSD-3-Clause (its binary wheels bundle image codecs under their own licences) | iPhone HEIC photos |
| [pystray](https://github.com/moses-palmer/pystray) | LGPL-3.0 | The notification-area (tray) icon |
| [icalendar](https://github.com/collective/icalendar) | BSD-2-Clause | Reading calendar (ICS) links |
| [recurring-ical-events](https://github.com/niccokunzmann/python-recurring-ical-events) | LGPL-3.0-or-later | Repeating calendar events |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) (optional) | Unlicense | Better YouTube search |

## Optional voice packages (`requirements-voice.txt`)

| Package | Licence | Used for |
|---|---|---|
| [NumPy](https://numpy.org) | BSD-3-Clause | Audio processing |
| [sounddevice](https://github.com/spatialaudio/python-sounddevice) | MIT | Microphone and the timer bell |
| [openWakeWord](https://github.com/dscripka/openWakeWord) | Apache-2.0 (code) | "Hey Jarvis" wake word |
| [faster-whisper](https://github.com/SYSTRAN/faster-whisper) | MIT | Local speech-to-text |
| `nvidia-cublas-cu12`, `nvidia-cudnn-cu12` (optional) | NVIDIA's licence | Local Whisper on an NVIDIA graphics card |

### Not included: Piper

[Piper](https://github.com/OHF-Voice/piper1-gpl) (`piper-tts`), the natural-sounding voice for spoken replies, is
licensed **GPL-3.0-or-later**. To keep the dashboard MIT-licensed it is not a required dependency. If you install it
yourself (`pip install piper-tts`), the dashboard uses it automatically; otherwise it speaks with the Windows voice.

## Models downloaded on first use

| Model | Licence | Notes |
|---|---|---|
| openWakeWord pre-trained "hey_jarvis" model | [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) | Non-commercial use only. © David Scripka. |
| Whisper speech models (faster-whisper conversions) | MIT | © OpenAI; converted by SYSTRAN. Only with local speech-to-text. |
| Piper voice `en_US-libritts_r-medium` (default, only if Piper is installed) | [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) | Trained on LibriTTS-R. From [rhasspy/piper-voices](https://huggingface.co/rhasspy/piper-voices). |

You can choose another Piper voice in Settings. Some have restrictive licences: for example `en_US-lessac` is trained
on a research-only dataset, and `hfc_female` / `hfc_male` are non-commercial. Check a voice's `MODEL_CARD` first.

## Online services

The widgets fetch public data from these services. Their own terms apply; no account or key is included.

| Widget | Service |
|---|---|
| Weather | [Open-Meteo](https://open-meteo.com) (forecast and city search) |
| News | Public RSS feeds (The Hindu, Times of India, NDTV, BBC World, Al Jazeera by default; change them in Settings) |
| Cyber threats | Public security feeds and advisories (e.g. CISA, NVD, BleepingComputer, Krebs on Security, The Record, SecurityWeek) |
| Markets | Yahoo Finance chart data (unofficial endpoint, personal use), CoinGecko, Frankfurter (currency rates) |
| Music / video | YouTube, played in the dashboard's own browser view, signed in with your own account if you choose |
| WhatsApp | WhatsApp Web, linked by QR code in the dashboard's own browser view |
| Calendar | Calendar links (ICS) you add, e.g. Google Calendar's secret address |
| Telegram | Telegram Bot API with your own bot token |
| AI, speech-to-text, Widget Studio | The provider you choose (Ollama locally, or Google Gemini, OpenAI-compatible services, Anthropic) with your own API key |

## Trademarks

YouTube, WhatsApp, Telegram, Windows and other names are trademarks of their owners. Sekar's Dashboard is not
affiliated with or endorsed by any of them.
