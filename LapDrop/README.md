# LapDrop

AirDrop-style file sharing for a **Windows laptop**. Run LapDrop on the laptop, scan its QR code with a phone on
the same Wi-Fi, and send photos, videos and documents of any size from the phone's browser. Nothing to install on
the phone, and nothing leaves your local network.

It works with any phone, tablet or computer that has a browser: iPhone, iPad, Android, Mac, Linux or another PC.

**Contents:** [Features](#features) · [Install](#install) · [Using it](#using-it) ·
[iPhone Share menu](#iphone-share-menu) · [No Wi-Fi](#no-wi-fi) · [Screen mirroring](#screen-mirroring-optional) ·
[Privacy and security](#privacy-and-security) · [Troubleshooting](#troubleshooting) · [From source](#from-source) ·
[Licence](#licence)

## Features

| | |
|---|---|
| **Phone to laptop** | Choose files on the phone; any size, several at once, with progress. They land in `Downloads\LapDrop` |
| **Laptop to phone** | Drop files on the laptop window; the phone sees them and taps **Download** |
| **Chat** | Messages across the network. Each one shows the sender's name and the device's address |
| **Share menu (iPhone)** | One-time setup of a Shortcut, then **Share → LapDrop** from Photos, Files or any app |
| **Hotspot mode** | No Wi-Fi? Use the phone's hotspot or Windows Mobile hotspot |
| **Screen mirroring** | Optional: shows the iPhone screen in a window on the laptop (AirPlay, through [UxPlay](#screen-mirroring-optional)) |
| **Start with Windows** | Optional, starts minimised |

## Install

### With the installer (recommended)

No Python needed. About 14 MB, installs for your user only, without administrator rights.

1. Open the [LapDrop release](https://github.com/sekar28/sekar-voyage/releases/tag/lapdrop-v1.0.1) and download into
   **one folder**: `LapDrop-Setup-1.0.1.exe`, `SekarsVoyage-CodeSigning.cer` and `Trust-Certificate.ps1`.
2. **Check the download** (recommended): `Get-FileHash .\LapDrop-Setup-1.0.1.exe` in PowerShell must print the
   SHA-256 shown on the release page.
3. **Trust the publisher** (once per PC, optional; the same certificate as my other apps): right-click
   `Trust-Certificate.ps1` → **Run with PowerShell**, then click **Yes** in the Windows warning.
4. **Run the installer.** If SmartScreen says *"Windows protected your PC"*, click **More info → Run anyway** (the
   certificate is self-made, so Microsoft doesn't know it yet). Tick *Start LapDrop when Windows starts* if you want.
5. **Windows Firewall:** the installer's option *Allow LapDrop through Windows Firewall on home (Private) networks*
   (ticked by default) asks once for administrator approval and adds the rule. Public networks stay blocked. If you
   skip it, Windows asks the first time LapDrop starts: tick **Private networks**. If phones still can't connect,
   LapDrop shows a red **Windows Firewall is blocking phones** box with a button to the settings.

> **Antivirus note:** Python apps packed into an .exe are sometimes flagged by machine-learning detections. Compare
> the SHA-256 with the release page. If it matches, it's a false positive; please report it at
> <https://www.microsoft.com/wdsi/filesubmission>.

## Using it

1. Start LapDrop on the laptop. Its window shows a QR code.
2. Connect the phone to the **same Wi-Fi** and point the camera at the code.
3. The phone opens LapDrop in its browser. The first time, it warns that the connection is not private: that is
   expected (LapDrop makes its own certificate). Choose **Advanced / Show details → continue**. If the phone still
   refuses, tick *Use the plain http link instead* under the QR code.
4. Tap **Choose files** to send. Received files appear in the laptop window and in `Downloads\LapDrop`.

Tips: add the phone page to your home screen; the link keeps working while the laptop's address stays the same.
**New code** makes a new link and stops the old one working.

## iPhone Share menu

A one-time setup on the iPhone or iPad. The same steps, with the address to copy, are in the laptop window
(*Send from the iPhone's Share menu*) and on the phone page (*Add LapDrop to the Share menu*).

1. Copy the **Share-menu address** shown there. It looks like
   `http://<laptop-name>.local:8765/d/<code>/api/upload`: **http**, port **8765**. Don't use the QR link (https, port
   8443): the Shortcuts app refuses LapDrop's self-made certificate.
2. In **Shortcuts**, tap **+** and name the shortcut **LapDrop**.
3. Tap **i** and switch on **Show in Share Sheet**; let it receive Images, Files and Media (or Any).
4. Add **Repeat with Each** with **Shortcut Input** as its input.
5. Inside the repeat, add **Get Contents of URL** and paste the address.
6. In that action's options: **Method** = POST, **Request Body** = **Form**.
7. **Add new field → File**, key **`file`**, value **Repeat Item**.
8. Tap **Done**. In Photos, **Share → LapDrop**. Allow local-network access the first time.

If the phone can't connect, the laptop's name may not resolve on that network: use the IP-address version shown just
below (it changes when the laptop's address does). **New code** changes both addresses, so update the shortcut after it.

## No Wi-Fi

- **Phone hotspot:** turn on Personal Hotspot and connect the laptop to it. The QR code updates by itself.
- **Laptop hotspot:** turn on Mobile hotspot in Windows (LapDrop has a button for the settings page), join it from
  the phone, then pick *Laptop hotspot* under Network. Windows only allows this while the laptop has a connection.

Transfers stay between the two devices and don't use mobile data.

## Screen mirroring (optional)

LapDrop can start **[UxPlay](https://github.com/FDH2/UxPlay)**, a separate open-source AirPlay receiver (GPL-3.0),
so the iPhone's **Control Centre → Screen Mirroring** shows the phone in a window on the laptop. UxPlay is **not
included**; the card says so until it finds `uxplay.exe` in `C:\msys64\ucrt64\bin` or on your `PATH`.

To build it: install [MSYS2](https://www.msys2.org), then in the UCRT64 shell
`pacman -S mingw-w64-ucrt-x86_64-{cmake,gcc,ninja,libplist,gstreamer,gst-plugins-base,gst-plugins-good,gst-plugins-bad,gst-libav}`,
clone UxPlay and build it with CMake (see UxPlay's README). Allow `uxplay.exe` in Windows Firewall when asked.

## Privacy and security

- Everything stays on your local network. No account, no cloud, no telemetry, no ads.
- Phones need the secret link from the QR code. The laptop's own controls only answer to a browser on the laptop.
- Anyone on the same network **who has the link** can send files, so use it on networks you trust, and press
  **New code** if a link was shared by mistake.
- Settings, the chat history and the certificate are kept in `%APPDATA%\LapDrop`; a log is in `lapdrop.log` there.

## Troubleshooting

| Problem | Try |
|---|---|
| The phone can't open the page | Same Wi-Fi? Windows Firewall must allow `LapDrop.exe` on the network's type: Start → *Allow an app through Windows Firewall* → Change settings → tick **Private** (home) for LapDrop.exe. A rule that covers only Public blocks a home network silently. A VPN on the laptop (NordVPN, ExpressVPN…) can also block local devices unless its local-network option is on |
| Share-menu shortcut fails | Use the **http** address with port **8765** (not the https QR link); the form needs a **File** field named `file`. The reason for a refused upload is written in `%APPDATA%\LapDrop\lapdrop.log` |
| "Connection not private" | Expected the first time; continue anyway, or use the plain http link |
| HTTPS link missing just after start | It appears about 10 seconds after LapDrop starts |

## From source

Python 3.10 or newer on Windows:

```
pip install -r requirements.txt
python lapdrop.py              # app window
python lapdrop.py --browser    # use your browser instead
```

`Start LapDrop.bat` starts it without a console. To build the installer: `packaging\build.ps1` (needs PyInstaller
and Inno Setup 6; it signs with a self-made certificate in your user store).

## Licence

[MIT](LICENSE). Third-party packages keep their own licences; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
AirDrop and AirPlay are trademarks of Apple Inc. LapDrop is not affiliated with or endorsed by Apple.
