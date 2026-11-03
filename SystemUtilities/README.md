# Sekar's System Utilities

A free, open-source PC care app for Windows 10 and 11: clean up junk, organise folders, check drivers, speed up a
slow PC, and **Jarvis**, an optional assistant you can type or talk to, which runs the same checks and always asks
before changing anything.

Everything runs on your PC. AI is optional: use a local model (Ollama), your own cloud key (OpenAI, Google Gemini,
Anthropic…), or no AI at all.

**Contents:** [What it does](#what-it-does) · [Install (installer)](#install-with-the-installer-recommended) ·
[Install from source](#install-from-source) · [Using it](#using-it) · [Set up AI (optional)](#set-up-ai-optional) ·
[Privacy](#privacy-in-short) · [Troubleshooting](#troubleshooting) · [Uninstall](#uninstall) ·
[For developers](#for-developers) · [Licence](#licence)

## What it does

| Section | Highlights |
|---|---|
| **Home** | Your PC's specs, live CPU / memory / battery, and a summary card from every section |
| **Clean-up** | Quick clean of always-safe junk (temp files, caches, old logs, driver installers, broken shortcuts…) with *See data*; scan any drive or folder for what's using space; clean-up suggestions with impact; optional AI review; duplicate versions like `report(1).pdf` |
| **Organiser** | Folder health check; a plan (rules or AI) for where loose files should go; optional deep analysis of documents (bills, KYC, bank…); *Organise for me* with preview, report and **undo** |
| **Drivers** | Installed drivers and their age; Windows Update driver offers with a restore point first; BIOS downgrades blocked; the right official tool for each driver |
| **Performance** | Live memory and CPU; background helpers that are safe to close; *Boost now*; *Clean RAM*; startup apps on/off; other quick wins |
| **Jarvis** | Ask in plain words ("what can I delete in Downloads?"), get a short report and a Yes / No / Review question. Background checks, alerts, learns your preferences on this PC only, voice with "Hey Jarvis" (source install) |

Safety first: deletions go to the Recycle Bin where possible, Windows and program folders are protected, organising
can be undone, drivers get a restore point, and nothing is closed, deleted, moved or installed without your
confirmation.

## Install with the installer (recommended)

You don't need Python: the installer contains everything the app needs and doesn't touch any Python you already
have.

1. Open the [latest release](https://github.com/sekar28/sekar-voyage/releases/latest) and download these three files
   into **one folder**:
   - `SystemUtilities-Setup-<version>.exe` — the installer
   - `SekarsVoyage-CodeSigning.cer` — the public certificate the installer is signed with
   - `Trust-Certificate.ps1` — adds that certificate to your Windows user account
2. **Check the download** (optional, recommended). In PowerShell, in that folder:

   ```powershell
   Get-FileHash .\SystemUtilities-Setup-1.0.1.exe
   ```

   The result must match the SHA-256 listed on the release page. If it doesn't, delete the file.
3. **Trust the publisher** (once per PC, optional). Right-click `Trust-Certificate.ps1` → **Run with PowerShell**,
   check that it shows *CN=Sekar's Voyage*, and click **Yes** in the Windows security warning. If scripts are blocked:

   ```powershell
   powershell -ExecutionPolicy Bypass -File .\Trust-Certificate.ps1
   ```

   This makes Windows show **Sekar's Voyage** as a verified publisher. You can skip it; the app works the same.
4. **Run the installer.** Because the file comes from the internet, Windows SmartScreen may say *"Windows protected
   your PC"*: the certificate is self-made and not yet known to Microsoft. Click **More info → Run anyway**, or first
   right-click the .exe → **Properties** → tick **Unblock** → **OK**.
5. Choose **Install for me only** (no administrator rights needed) and finish. Start the app from the Start menu.

The installer is the **typing-only edition**: Jarvis works by typing; there is no "Hey Jarvis" wake word or
speech-to-text. For voice, install from source.

> **Antivirus note:** Python apps packed into an .exe are sometimes flagged by machine-learning detections such as
> `Trojan:Win32/Bearfoos.A!ml`. If that happens, compare the file's SHA-256 with the release page. If it matches,
> it's a false positive; please report it at <https://www.microsoft.com/wdsi/filesubmission>. If it doesn't match,
> delete the file.

## Install from source

For developers, or if you want the voice features.

**Needs:** Windows 10/11 (64-bit), [Python 3.12](https://www.python.org/downloads/) (tick *Add python.exe to PATH*),
and Microsoft Edge WebView2 (already part of Windows 10/11).

1. Get the code: **Code → Download ZIP** on GitHub and unzip it, or:

   ```powershell
   git clone https://github.com/sekar28/sekar-voyage.git
   ```

2. Install the packages:

   ```powershell
   cd sekar-voyage\SystemUtilities
   pip install -r requirements.txt
   ```

3. Optional, voice (wake word and speech-to-text):

   ```powershell
   pip install -r requirements-voice.txt
   ```

4. Optional, a natural-sounding voice for spoken replies. Piper is GPL-3.0 and not included; see
   [third-party notices](THIRD_PARTY_NOTICES.md). Without it the Windows voice is used.

   ```powershell
   pip install piper-tts==1.8.0
   ```

5. Start it: double-click `Run System Utilities.bat`, or run `pythonw app.py`.

Command-line options: `--tray` (start hidden in the notification area), `--no-monitor` (no background checks),
`--no-voice`, `--debug`, `--serve` (developer mode: the UI in a browser at http://127.0.0.1:8765/?serve=1).

## Using it

1. **Home** shows your PC and how much space you can free safely. Press **Clean now** for the quick win.
2. **Clean-up → Quick clean**: tick what to remove and press **Clean**. Pick a drive in the sidebar, or use
   **Scan a folder…**, to see what takes space, then review the suggestions.
3. **Organiser**: pick a folder (Downloads, Documents… or **Pick a folder**) to get its health check, press
   **AI plan** (or **Suggest plan** without AI), review it, then **Organise for me**. Every move can be undone.
4. **Drivers**: see old drivers and install Windows Update offers (a restore point is made first).
5. **Performance**: close safe-to-close background apps, **Clean RAM**, and turn startup apps off.
6. **Jarvis**: open the AI assistant card at the bottom of the sidebar and type, for example, *"what can I delete in
   Downloads?"* or *"why is my PC slow?"*. Jarvis answers with a short report and asks **Yes / No / Review** before
   doing anything. With voice installed, say **"Hey Jarvis"** or press **Ctrl+Alt+J**.

Some cleaning needs administrator rights; use **Restart as administrator** when the app offers it. Closing the window
keeps the app in the system tray while background monitoring is on; right-click the tray icon for *Quit*.

Full details for every screen: **[user guide](docs/HELP.md)**.

## Set up AI (optional)

The app works without AI. To add it, open **AI settings** (sidebar), choose a provider and press **Test connection**:

| Provider | What you need |
|---|---|
| **Ollama** (local, free, private) | Install [Ollama](https://ollama.com) and a model, e.g. `ollama pull qwen3:8b` |
| **Google Gemini** | An API key from Google AI Studio |
| **OpenAI** or another OpenAI-compatible service | An API key from that service |
| **Anthropic (Claude)** | An API key from the Anthropic Console |

Keys are yours, entered on your PC and stored in **Windows Credential Manager**. They are never written to files or
shared. Before any cloud AI request, the app shows what will be sent and roughly how many tokens it uses.

## Privacy in short

- No account, no telemetry, no ads. The app never phones home.
- With a **cloud** AI or speech service, the app sends what that feature needs (file and folder names, sizes, short
  document excerpts only for deep analysis, your spoken request) to the provider **you** chose, with **your** key,
  and tells you before it does.
- What Jarvis learns stays in `%LOCALAPPDATA%\StorageAnalyzer\agent\` on that PC: never synced, never shared.

## Troubleshooting

| Problem | Try |
|---|---|
| "Windows protected your PC" | See step 4 of [the installer steps](#install-with-the-installer-recommended). |
| Antivirus flags the installer | See the antivirus note above. |
| Some items say *Needs administrator* | Use **Restart as administrator**. |
| AI features say AI isn't set up | **AI settings** → choose a provider → **Test connection**. |
| The window won't open | It may be running in the tray: start it again (it comes to the front) or use the tray icon. |

More in the [user guide](docs/HELP.md#troubleshooting).

## Uninstall

**Settings → Apps → Sekar's System Utilities → Uninstall** (or delete the folder if you ran it from source). Your
settings and what Jarvis learned stay in `%LOCALAPPDATA%\StorageAnalyzer\`; delete that folder too for a full
clean-up, and remove `SystemUtilities/…` entries in **Credential Manager → Windows Credentials**. To remove the
certificate: run `certmgr.msc` and delete *Sekar's Voyage* from **Trusted Root Certification Authorities** and
**Trusted Publishers**.

## For developers

- `app.py` is the window and the JavaScript API; `ui/` is the interface (HTML / CSS / JS, no build step).
- Feature modules: `quickclean.py`, `cleanup.py`, `core.py` (scanner), `organiser.py`, `mover.py`, `content.py`,
  `versions.py`, `drivers.py`, `perf.py`, `sysinfo.py`, `agent.py` / `agent_memory.py` / `agent_server.py` (Jarvis),
  `voice.py` / `voice_host.py` / `tts.py` / `bell.py` (voice), `llm.py` / `llm_anthropic.py` (AI providers).
  `llm.py`, `llm_anthropic.py`, `secrets_store.py`, `bell.py` and `voice.py` are small aliases for
  [`../shared/sekar_common`](../shared/sekar_common).
- **Build the installer:** `packaging\build.ps1 -Version 1.0.1` (needs PyInstaller and Inno Setup 6). It bundles the
  app, runs `tools/check_release.py` (fails if personal data, model files or Piper would ship), signs the .exe and the
  installer with a self-signed code-signing certificate from your Windows user store (created on the first run),
  and writes everything to `packaging\Output\`. Release builds use a PyInstaller bootloader compiled from source,
  which antivirus tools flag less often.

## Licence

[MIT](LICENSE) for Sekar's System Utilities' own code. Third-party packages and models keep their own licences; see
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
