# Sekar's Voyage

Free, open-source tools I build with AI, for everyday Windows users. Each project lives in its own folder with its
own README.

| Project | What it is | Get it |
|---|---|---|
| [**Sekar's System Utilities**](SystemUtilities/) | Windows 10/11 PC care: clean up junk, organise folders, check drivers, speed up a slow PC, plus **Jarvis**, an optional assistant that always asks before changing anything | [Download the installer](https://github.com/sekar28/sekar-voyage/releases/latest) · [Install & use](SystemUtilities/README.md) · [User guide](SystemUtilities/docs/HELP.md) |

## Repository layout

```
sekar-voyage/
├── SystemUtilities/     the System Utilities app (Python + HTML/CSS/JS)
│   ├── docs/HELP.md     full user guide
│   ├── packaging/       scripts that build and sign the Windows installer
│   └── tools/           release checks
└── shared/
    └── sekar_common/    code shared by my apps: AI providers, key storage (Windows Credential Manager), voice
```

`shared/` must sit next to the app folder: the app loads it from `../shared`. Clone or download the **whole**
repository, not only the `SystemUtilities` folder.

## Licence

[MIT](LICENSE). Third-party packages and models keep their own licences; see each project's
`THIRD_PARTY_NOTICES.md`.
