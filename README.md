# Sekar's Voyage

Free, open-source tools I build with AI, for everyday Windows users. Each project lives in its own folder with its
own README.

| Project | What it is | Get it |
|---|---|---|
| [**Sekar's System Utilities**](SystemUtilities/) | Windows 10/11 PC care: clean up junk, organise folders, check drivers, speed up a slow PC, plus **Jarvis**, an optional assistant that always asks before changing anything | [Download the installer](https://github.com/sekar28/sekar-voyage/releases/latest) · [Install & use](SystemUtilities/README.md) · [User guide](SystemUtilities/docs/HELP.md) |
| [**Sekar's Dashboard**](Dashboard/) | A voice-controlled AI dashboard for a second monitor: photo frame, music and YouTube, weather, news, markets, cyber-threat briefings, timers, tasks and calendar. Say "Hey Jarvis", or type. Widget Studio builds new widgets from a description | [Install & use](Dashboard/README.md) (run from source) |

The two apps work together: with System Utilities installed, you can ask the Dashboard PC-care questions ("why is
my PC slow?") and it passes them on. Each also works on its own.

## Repository layout

```
sekar-voyage/
├── SystemUtilities/     the System Utilities app (Python + HTML/CSS/JS)
│   ├── docs/HELP.md     full user guide
│   ├── packaging/       scripts that build and sign the Windows installer
│   └── tools/           release checks
├── Dashboard/           the second-monitor dashboard (Python + HTML/CSS/JS)
│   ├── widgets/         one module per tile (weather, news, music, tasks…)
│   └── ui/              the interface, including Widget Studio's sandbox SDK
└── shared/
    └── sekar_common/    code shared by my apps: AI providers, key storage (Windows Credential Manager), voice
```

`shared/` must sit next to the app folders: both apps load it from `../shared`. Clone or download the **whole**
repository, not only one app's folder.

## Licence

[MIT](LICENSE). Third-party packages and models keep their own licences; see each project's
`THIRD_PARTY_NOTICES.md`.
