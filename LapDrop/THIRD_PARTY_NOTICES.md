# Third-party notices

LapDrop's own code is MIT-licensed (see [LICENSE](LICENSE)). It uses the open-source packages below, each under its
own licence. None of them is in this repository. The **installer** bundles the Python packages (plus their own
dependencies, such as cffi, pythonnet and bottle, each under its own permissive licence) and the Python runtime
(PSF licence), packed with [PyInstaller](https://pyinstaller.org) (GPL-2.0 with the bootloader exception).

## Python packages (`requirements.txt`)

| Package | Licence | Used for |
|---|---|---|
| [segno](https://github.com/heuer/segno) | BSD-3-Clause | The QR code |
| [cryptography](https://github.com/pyca/cryptography) | Apache-2.0 or BSD-3-Clause | The self-made certificate for the https link |
| [pywebview](https://github.com/r0x0r/pywebview) | BSD-3-Clause | The app window |

## Not included: UxPlay

[UxPlay](https://github.com/FDH2/UxPlay), the AirPlay receiver used for screen mirroring, is licensed **GPL-3.0**
and uses GStreamer (LGPL). It is a separate program: LapDrop only starts it if you have installed it yourself, and
neither this repository nor the installer contains it.

## Trademarks

AirDrop, AirPlay, iPhone, iPad and Mac are trademarks of Apple Inc. Windows is a trademark of Microsoft. LapDrop is
not affiliated with or endorsed by either.
