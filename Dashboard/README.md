# Sekar's Dashboard

A voice-controlled AI dashboard for a **second monitor** on Windows 10/11. Instead of mirroring or extending your
screen, turn a spare or portable display into a photo frame with everything you like around it: time zones,
weather, music and YouTube, news, markets, cyber-threat briefings, timers, tasks and your calendar. Say
**"Hey Jarvis"** and ask for things, or type them.

AI is optional: a local model (Ollama), your own cloud key (Google Gemini, OpenAI-compatible, Anthropic), or none.

**Contents:** [Features](#features) · [Install](#install) · [First start](#first-start) · [Using it](#using-it) ·
[Voice commands](#voice-commands) · [Settings](#settings) · [Widget Studio](#widget-studio) ·
[Telegram (optional)](#telegram-optional) · [Privacy](#privacy) · [Troubleshooting](#troubleshooting) ·
[For developers](#for-developers) · [Licence](#licence)

## Features

| Tile | What it shows |
|---|---|
| **Top bar** | Clock, date, weather, two world clocks, mic button, ask-or-command box, mute, layout and settings |
| **Photos** | A slideshow of your Pictures folder (including iPhone HEIC and online-only OneDrive photos); full screen on request |
| **Music** | Search and play songs or videos from YouTube, with play / pause / next |
| **Markets** | Shares, currencies and crypto you choose |
| **News** | Headlines from RSS feeds you choose; **Explain** reads out a summary of a story |
| **Cyber threats** | Latest security news and advisories; **Brief me** gives a spoken AI summary |
| **Timers & alarms** | Rings until you acknowledge it, turns red near the end, flashes when done |
| **Tasks** | To-dos with how long they've been pending, due dates and reminders |
| **Agenda** | Your calendars (ICS links), or a plain calendar if none is linked |
| **WhatsApp** | WhatsApp Web inside the dashboard, linked by QR code |
| **PC monitor** | CPU, memory, GPU and disk at a glance |
| **Assistant** | What Jarvis heard and answered |

Plus **Widget Studio**: describe a widget in plain words and the AI builds it for you.

## Install

There is no installer for the dashboard yet; run it from source.

**Needs:** Windows 10/11 (64-bit), [Python 3.12](https://www.python.org/downloads/) (tick *Add python.exe to PATH*),
Microsoft Edge WebView2 (already part of Windows 10/11). A second monitor is recommended but not required.

1. Get the code: **Code → Download ZIP** on GitHub and unzip it, or:

   ```powershell
   git clone https://github.com/sekar28/sekar-voyage.git
   ```

   Keep the folder structure: the dashboard loads shared code from `../shared`.
2. Install the packages:

   ```powershell
   cd sekar-voyage\Dashboard
   pip install -r requirements.txt
   ```

3. Optional, voice ("Hey Jarvis", speech-to-text, the timer bell):

   ```powershell
   pip install -r requirements-voice.txt
   ```

   With an NVIDIA graphics card you can also run local speech-to-text on the GPU:
   `pip install nvidia-cublas-cu12 nvidia-cudnn-cu12` (a large download).
4. Optional, a natural-sounding voice for replies (Piper, GPL-3.0, not included; without it the Windows voice is
   used): `pip install piper-tts`
5. Start it: double-click `Run Dashboard.bat`, or run `pythonw app.py`.

Command-line options: `--window` (a normal window instead of full screen), `--debug` (with browser dev tools),
`--serve` (developer mode: the UI in a browser at http://127.0.0.1:8770/?serve=1).

## First start

1. The dashboard opens **full screen on your second monitor** (on your main screen if you have only one). A tray
   icon appears; **Ctrl+Alt+D** or the tray icon brings it back if it goes behind other windows.
2. Open **Settings** (gear icon, top right) and set:
   - **Weather:** your city.
   - **World clocks:** two time zones for the top bar.
   - **Photo folders:** blank uses your Pictures folder.
   - **AI:** choose Ollama (local) or a cloud provider and enter your key (see [Settings](#settings)).
   - **Speech-to-text:** cloud (Gemini, faster and more accurate) or local Whisper.
3. Optional: **YouTube** sign-in, **WhatsApp** QR link and **calendar** links. All of them stay inside the
   dashboard's own browser profile on your PC.

## Using it

- **Talk:** say **"Hey Jarvis"**, then your request. Or click the mic button / press **Ctrl+Alt+Space** and speak.
- **Type:** use the *Ask or command…* box in the top bar.
- **Maximise a tile:** the ⤢ button on any tile; ask "show photos full screen".
- **Mute spoken replies:** the speaker button in the top bar.
- **Change the layout:** **Edit layout** (top bar) lets you move, resize, add or remove widgets.
- **Timers:** "set a timer for 10 minutes". When it rings, click the tile or say "stop" to acknowledge.
- **Music turns down** while you speak to Jarvis and while it answers (the level is a setting).

## Voice commands

Examples (typed commands work the same):

| Say | What happens |
|---|---|
| "Play Believer by Imagine Dragons" | Finds and plays it in the Music tile |
| "Pause" / "next song" / "volume down" | Controls the music |
| "How's the market?" | Reads out your Markets tile |
| "Brief me on cyber attacks" | Spoken AI summary of the latest threats |
| "Explain the second news story" | Reads and explains a headline |
| "What's the weather?" | Current weather and the next hours |
| "Set a timer for 5 minutes" / "remind me at 7 am to call mum" | Timers and reminders; "stop" or "snooze for 5 minutes" while it rings |
| "Add a task buy milk by Friday" / "what are my tasks" / "mark buy milk as done" | Tasks |
| "Show photos full screen" / "next photo" | Photos |
| "Open WhatsApp" | Opens the WhatsApp tile |
| "Clean up my PC" / "why is my PC slow?" | Passed to [System Utilities](../SystemUtilities/) if it's installed |

Anything else goes to the AI you chose, which answers or picks the right action.

## Settings

Open **Settings** with the gear icon. Among other things you can set:

| Area | What you set |
|---|---|
| **Screen** | Which monitor the dashboard uses (*Show the dashboard on*) |
| **AI** | Provider: Ollama (install [Ollama](https://ollama.com), then e.g. `ollama pull qwen3:8b`), Google Gemini, an OpenAI-compatible service, or Anthropic, plus the model |
| **Voice** | Voice on/off, wake word, speech-to-text mode (cloud or local Whisper), spoken replies and the Piper voice |
| **Widgets** | Weather city and units, world clocks, news feeds, market symbols, photo folders, calendar links |
| **Widget Studio** | Which AI provider and model builds widgets |
| **Telegram** | Bot token and pairing (see below) |

API keys are entered on your PC and stored in **Windows Credential Manager**, never in files. Settings live in
`%LOCALAPPDATA%\Dashboard\settings.json`.

## Widget Studio

Click **Edit layout** (top bar), then **✨ Create widget…**, or ask Jarvis to create one. Describe what you want (for example *"a countdown to New Year"* or
*"a cricket live score"*), and the AI writes a small widget, tests that its data sources work, and lets you place it.
Widgets run in a locked-down sandbox: they can only fetch the sources they declared, and your API keys never reach
them. It needs your own AI key; Google Gemini has a free tier (key from aistudio.google.com/apikey).

## Telegram (optional)

Get alerts for overdue tasks and send commands from your phone:

1. In Telegram, message **@BotFather**, create a bot and copy its token.
2. In **Settings → Telegram**, paste the token. The dashboard shows a one-time `/pair` code.
3. Send that `/pair …` message to your bot. Only that paired chat can command the dashboard.

Then you can add, complete or snooze tasks by message and get a daily digest. With System Utilities installed,
`/pc <question>` asks it read-only questions; nothing on your PC can be changed from Telegram.

## Privacy

- No account, no telemetry. The dashboard only contacts the services its widgets need (weather, news, markets,
  YouTube…) and the AI or speech provider **you** chose, with **your** key.
- Your sign-ins (YouTube, WhatsApp) stay in the dashboard's own browser profile in `%LOCALAPPDATA%\Dashboard\`.
- Cloud speech-to-text sends the recording of your request to the provider you chose; local Whisper keeps it on
  your PC.

## Troubleshooting

| Problem | Try |
|---|---|
| "Voice needs: pip install …" in the top bar | `pip install -r requirements-voice.txt`, then restart. |
| "Hey Jarvis" isn't heard | Check the mic in Windows sound settings; quiet headset mics may need a higher input level. Use the mic button meanwhile. |
| The dashboard disappeared | Press **Ctrl+Alt+D** or click the tray icon. Starting it again also brings it back. |
| It opens on the wrong screen | **Settings → Show the dashboard on**, or start with `--window`. |
| Replies use the robotic Windows voice | Install Piper: `pip install piper-tts` (optional). |
| AI answers say AI isn't set up | **Settings → AI**: choose a provider and enter your key. |
| Widget Studio says quota exceeded | Your AI provider's free quota ran out; try later or choose another model. |

## For developers

- `app.py` is the window, settings and the JavaScript API; `ui/` is the interface (HTML / CSS / JS, no build step).
- `assistant.py` turns text into actions (rules for common commands, otherwise the AI). `widgets/` has one module
  per tile. `widgetsmith.py` and `ui/widget-sdk.js` are Widget Studio. `telegram_link.py` is the Telegram bot.
  `pcagent.py` talks to System Utilities' local agent. `tts.py` is spoken replies, `tray.py` the tray icon.
- `llm.py`, `llm_anthropic.py`, `secrets_store.py`, `alarm.py` and `voice.py` are small aliases for
  [`../shared/sekar_common`](../shared/sekar_common), which System Utilities uses too.

## Licence

[MIT](LICENSE) for the dashboard's own code. Third-party packages, models and services keep their own licences and
terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
