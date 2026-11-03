# Sekar's System Utilities — User guide

Sekar's System Utilities keeps a Windows PC tidy and quick: it finds junk, organises folders, checks drivers and
performance, and includes **Jarvis**, an assistant you can type or talk to. Nothing is deleted, moved, closed or
installed without your confirmation.

**Contents:** [Getting started](#getting-started) · [Home](#home) · [Clean-up](#clean-up) · [Organiser](#organiser) ·
[Drivers](#drivers) · [Performance](#performance) · [Jarvis assistant](#jarvis-assistant) · [AI settings](#ai-settings) ·
[Privacy and your data](#privacy-and-your-data) · [Troubleshooting](#troubleshooting) · [Uninstalling](#uninstalling)

---

## Getting started

1. Start **Sekar's System Utilities** from the Start menu (or `Run System Utilities.bat`).
2. The sidebar has five sections — **Home, Clean-up, Organiser, Drivers, Performance** — your drives, and the
   **AI assistant** card at the bottom.
3. The app follows your Windows light/dark theme; the button under the AI card switches it (Auto / Light / Dark).
4. Some cleaning (Windows temp files, Windows Update leftovers) needs administrator rights: use **Restart as
   administrator** when the app offers it.

**Closing the window** while background monitoring is on keeps the app in the notification area (system tray), so
Jarvis can keep an eye on your PC. Right-click the tray icon for *Open*, *Assistant*, *Monitor in the background*
and *Quit*.

---

## Home

- **Greeting and PC summary:** your PC model and Windows version, and how much space can be freed safely right now
  (with a **Clean now** button).
- **Specs:** processor, memory, graphics, storage, Windows and power, with live CPU, memory and battery readings.
- **Drive rings:** how full each drive is.
- **Section cards:** Clean-up, Organiser, Drivers and Performance each show their key numbers and a button to open them.

---

## Clean-up

### Quick clean

Always-safe junk, measured when you open it. Tick what you want and press **Clean**.

| Item | What it is | Notes |
|---|---|---|
| Temporary files (yours) | Leftovers from apps and installers | Files in use are skipped |
| Windows temporary files | Temp files from Windows and installers | Needs administrator |
| Browser caches | Chrome, Edge, Brave, Firefox caches | You stay signed in; close the browser to clean fully |
| Graphics shader caches | Pre-compiled shaders | Rebuilt automatically |
| Crash dumps & error reports | Saved when apps crash | Only useful when troubleshooting |
| Thumbnail cache | Explorer picture previews | Rebuilt as you browse |
| Windows Update leftovers | Updates already installed | Needs administrator |
| Driver installer downloads | NVIDIA / AMD driver setup copies | Installed drivers keep working |
| App log files | App logs older than 7 days | Recent logs are kept |
| App temp files | Microsoft Store apps' temp and web caches | Recreated as needed |
| Windows log files | Setup / update / servicing logs older than 7 days | Needs administrator |
| Broken shortcuts | Desktop, Start Menu and Recent shortcuts to things that no longer exist | Go to the **Recycle Bin** (restorable). Shortcuts to an unplugged drive are left alone |
| Windows setup files | Your previous Windows version and upgrade leftovers | **Unticked by default.** Removed with Windows' own Disk Cleanup; afterwards you can't go back to the previous Windows version |
| Recycle Bin | Files you already deleted | **Unticked by default.** Emptying it is permanent |

**See data** on any item lists its folders and largest files; click a row to open it in Explorer.

Not included on purpose: registry cleaning (no real speed benefit, risk of breaking apps), browser history and
cookies (they'd sign you out of sites), and the Windows Installer cache (apps need it to repair and uninstall).

### Scanning a drive or folder

Click a drive in the sidebar, or **Scan a folder…** (also **Scan another folder** next to the filter box). The scan is
shared by Clean-up and Organiser.

- **Browse:** a size chart and list; click folders to go deeper, right-click for actions, **Open in Explorer**.
  *Largest files* lists the biggest files in the scan. Online-only cloud files (OneDrive, iCloud) are shown separately
  and never downloaded.
- **Find clean-up candidates:** groups what can go by risk — **Safe**, **Worth reviewing**, **Caution**, **Keep** — with
  the impact of removing each and the right action (clean contents, Recycle Bin, or *Free up space* for cloud files).
- **AI review:** asks your AI about large folders the rules don't recognise. AI can be wrong — check before deleting.
- **Find duplicate versions:** files like `name(1).pdf`, `name (2).exe` compared **by content**; only true copies are
  offered, the original is kept, copies go to the Recycle Bin.

---

## Organiser

1. Pick a folder (Downloads, Documents, Desktop… or **Pick a folder**).
2. The **health check** scores how tidy it is and lists loose files, duplicates, copies and versions, empty and deeply
   nested folders. Duplicates can be removed from here (identical content only, one copy always kept).
3. **AI plan** (or **Suggest plan** with AI off) explains what will happen and suggests a folder structure and where
   each loose file should go.
   - Optional **deep analysis** sorts documents (PDF, Word, Excel, text) into *Bills & invoices, KYC & identity,
     Bank & tax, Insurance & medical, Work, Education, Property & legal, Travel, Manuals…* It reads a short excerpt
     only when a file's name says nothing, and never images or videos. With a cloud AI you can keep the reading on
     this PC (local model) or send names only.
   - The dialog compares token use / cost for each option.
4. **Organise for me** shows a preview (untick anything), moves the files, then shows what was achieved and which
   files were left and why. **Undo** puts everything back.

**Deep analyse & classify** and **Find duplicate versions** are also available as separate tiles.

Drive roots, your user folder, app data and Windows / program folders can't be organised automatically.

---

## Drivers

- **List:** your hardware drivers by group, with version and age. Age alone doesn't mean outdated.
- **Click any driver** for details, whether Windows Update has something for it, and the best official place to
  update it (Intel Driver & Support Assistant, NVIDIA app, AMD Software, or your PC maker's support page for
  laptop-customised drivers such as Realtek audio).
- **Windows Update:** driver offers matched to your hardware. **Install selected** creates a restore point first and
  asks for administrator permission. Firmware is marked; offers *older* than your installed BIOS are blocked.
- **Update everything safely:** installs Windows Update's driver offers, then opens each official vendor tool. No
  third-party driver sites are ever used.

---

## Performance

- **Live gauge:** memory and CPU, process count, time since restart.
- **Safe to close:** background helpers with no window (updaters, tray helpers, apps still running after you closed
  them). They start again on their own when needed.
- **Open apps:** closing asks the app to quit normally, so it can ask you to save; *Force close* only if you confirm.
- **Other background processes:** not on the safe list — close only if you know what they are (*Explain* asks your AI).
- **Startup apps:** switch apps on/off at sign-in (the same switch Task Manager uses; nothing is uninstalled).
- **Boost now:** closes the ticked helpers and cleans RAM, showing memory before → after.
- **Clean RAM:** asks apps to give back memory they aren't using (temporary; most useful above ~80%). *Also clear
  standby cache* needs administrator.
- **Quick wins:** temp files, restart reminder, power mode.
- Windows, services and Sekar's System Utilities itself are listed for information and never offered for closing.

---

## Jarvis assistant

Open **Jarvis assistant** in the sidebar (under AI settings).

### Talking to Jarvis

Type or say requests in plain words, for example:

- "How's my PC?" — a full check-up
- "Clean my junk" · "What can I delete in Downloads?" · "Old bills I can delete?"
- "Organise my Downloads" · "Find duplicates in Documents" · "Undo"
- "Boost my PC" · "Clean RAM" · "What processes are running?" · "Any orphan processes?"
- "Any suspicious programs?" · "Which startup apps can I remove?" · "Check my drivers"
- "Never suggest deleting KYC documents" · "What have you learned?"

Jarvis runs the same checks as the buttons and answers in a few sentences. Anything that would **change** your PC is
asked as a question with **Yes / No / Review**:

- **Yes** (or say "yes", "do it") carries it out and reports the result.
- **No** leaves everything as it is.
- **Review** ("show me") opens the matching screen so you can choose by hand.

A question waits 5 minutes. Long jobs (scans, organising plans, driver checks) answer right away and report when done.

### Voice

- **With Sekar's Dashboard app running** (if you have it), it listens for "Hey Jarvis" and passes PC requests to System
  Utilities. Its log labels those answers *Sekar's System Utilities*.
- **Without Sekar's Dashboard**, Sekar's System Utilities listens for "Hey Jarvis" itself (setting: *Voice*), speaks replies and
  alerts, and after a question listens once more so you can just say "yes".
- **Push-to-talk:** the mic button in the Jarvis panel, or **Ctrl+Alt+J** anywhere.
- *Speak replies and alerts* turns speech off. *Voice → Off* turns the microphone off.
- Speech-to-text uses your cloud key (e.g. Gemini) and/or local Whisper; spoken replies use Piper if installed,
  otherwise the Windows voice.

### Background monitoring

With *Watch my PC in the background* on, Jarvis checks quietly and tells you once when something needs attention:

| Check | When it speaks up |
|---|---|
| Memory | over 85% for 10 minutes |
| Junk | over 1 GB can be cleared |
| Loose files | 30 or more in Downloads or Desktop |
| Disk space | C: under 10% free |
| Background helpers | using over 1 GB |
| Drivers | Windows Update has driver updates |
| Restart | not restarted for 7+ days |

**Critical alerts** ring a bell once (and show in red):

- a program that looks **suspicious** (e.g. a Windows-like name running from Temp, an invalid signature) — once per
  program; Jarvis offers a Microsoft Defender scan and never calls anything malware;
- **CPU, memory or graphics card above 95%** for about a minute;
- **any drive more than 98% full**.

Each critical alert rings once per occurrence, and again only after the problem has cleared and come back.

### What Jarvis learns

On each PC separately, Jarvis learns from your answers and habits:

- **Documents:** when files arrive and when you open them, so it can say "12 old bills, not opened for 60+ days — you
  usually delete these". Say no twice to a kind (e.g. KYC) and it stops suggesting it.
- **Programs:** which run every day, which you actually use, and which look suspicious; startup apps you never open.
- **Habits:** e.g. "you usually clean up on Mondays".

**What Jarvis has learned** (in the panel) shows every rule, answer and flag, with buttons to change or forget each
one, or **Forget everything**.

---

## AI settings

Click **AI settings** in the sidebar card. The AI switch turns AI off entirely (rules only).

| Provider | Notes |
|---|---|
| **Ollama** (local) | Free, nothing leaves your PC. Install [Ollama](https://ollama.com) and a model (e.g. `qwen3:8b`). |
| **OpenAI-compatible** | OpenAI, **Google Gemini**, Groq and others: paste the base URL (presets included) and your API key. |
| **Anthropic** | Claude models with your Anthropic API key. |

- **Test connection** checks the key and lists the available models.
- Keys are stored in **Windows Credential Manager** (entries starting `SystemUtilities/`), never in plain files.
- With a cloud provider, the app shows the estimated tokens / cost before AI features run.

---

## Privacy and your data

- No account, no telemetry, no ads; the app never contacts a server of its own.
- **Cloud AI / speech (only if you set them up):** file and folder names, sizes and dates; short document excerpts only
  for deep analysis (unless you keep that local); process names and paths for *Explain*; your recorded request for
  cloud speech-to-text. Local options (Ollama, local Whisper) keep everything on your PC.
- **Jarvis's memory** never goes to the AI — only short rules like "user keeps KYC documents".

**Where things are kept** (all under `%LOCALAPPDATA%\StorageAnalyzer\`):

| Path | What |
|---|---|
| `settings.json` | Your settings |
| `content_cache.json` | Document classifications, so files aren't analysed twice |
| `undo\` | Undo records for organising |
| `agent\memory.db` | What Jarvis has learned |
| `agent.json` | The local link the Dashboard uses (port + secret token, this user only) |
| `last_request.wav` | Your latest spoken request (overwritten each time) |

API keys: Windows Credential Manager. "Start with Windows": the `SystemUtilities` value under
`HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.

---

## Troubleshooting

| Problem | Try |
|---|---|
| Some items say *Needs administrator* | Use **Restart as administrator**. |
| Browser caches don't clean fully | Close the browser first. |
| Setup says "Windows protected your PC" (SmartScreen) | The installer is signed with a self-made certificate that Microsoft doesn't know yet. Check its SHA-256 against the release page, then right-click it → **Properties** → tick **Unblock**, or click **More info → Run anyway**. |
| Defender flags `Trojan:Win32/Bearfoos.A!ml` or similar `!ml` | A machine-learning guess that is common for Python apps packed into an .exe. Compare the SHA-256 with the release page; if it matches it is a false positive — please report it at microsoft.com/wdsi/filesubmission. If it doesn't match, delete the file. |
| No voice / no "Hey Jarvis" in the installed app | The installer is the typing-only edition. For voice, run from source with `requirements-voice.txt`. |
| "Hey Jarvis" doesn't respond | Check *Voice* in the Jarvis panel and its status line; if the Dashboard is open, it is the one listening. Try **Ctrl+Alt+J**. |
| Voice says packages are missing | `pip install -r requirements-voice.txt` |
| Replies use the robotic Windows voice | Install Piper: `pip install piper-tts` (optional). |
| AI features say AI isn't set up | Open **AI settings**, choose a provider, **Test connection**. |
| Jarvis keeps suggesting something you want kept | Say "never suggest …", or use *What Jarvis has learned*. |
| The window won't open (already running in the tray) | Starting it again brings the running copy to the front, or use the tray icon. |

---

## Uninstalling

1. Uninstall from **Settings → Apps** (or delete the app folder if you ran it from source).
2. Optional clean-up of your data:
   - delete `%LOCALAPPDATA%\StorageAnalyzer\`;
   - in **Credential Manager → Windows Credentials**, remove entries starting `SystemUtilities/`;
   - turn off *Start with Windows* first (or remove the `SystemUtilities` value from
     `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`).

---

Sekar's System Utilities is free software under the [MIT licence](../LICENSE). Third-party components: see
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). It comes with no warranty — keep backups of important files.
