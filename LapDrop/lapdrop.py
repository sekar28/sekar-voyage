"""LapDrop - AirDrop-style file drop for this laptop.

Run it, scan the QR code with a phone on the same Wi-Fi, and send files,
photos, notes or links to the laptop from the phone's browser. Nothing to
install on the phone. Files land in Downloads\\LapDrop.

    python lapdrop.py             app window (falls back to the browser)
    python lapdrop.py --browser   open in the default browser
    python lapdrop.py --headless  server only

How access is limited:
  * The laptop page ("/" and "/admin/api/...") answers only to this PC.
  * Other devices must use the secret link in the QR code ("/d/<code>/").
    "New code" on the laptop page makes old links stop working.
  * The QR link is https (port 8443) with a certificate this laptop makes for
    itself, so the phone shows a warning the first time: choose to continue.
    A plain http link (port 8765) is still there as a fallback.
"""
from __future__ import annotations

import argparse
import hmac
import io
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

APP = "LapDrop"
PORT = 8765
# Installed build (PyInstaller): bundled files are unpacked under sys._MEIPASS.
HERE = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
UI = HERE / "ui"
CONFIG_DIR = Path(os.environ.get("APPDATA") or Path.home()) / APP
CONFIG_FILE = CONFIG_DIR / "config.json"
OUTBOX = CONFIG_DIR / "outbox"          # files waiting for the phone to fetch
TLS_PORT = 8443                         # https, for phones that refuse plain http
CERT = CONFIG_DIR / "cert.pem"
KEY = CONFIG_DIR / "key.pem"
CERT_META = CONFIG_DIR / "cert.json"
CHUNK = 1024 * 1024
MAX_NOTE = 5000
MAX_NOTES = 300
LIST_LIMIT = 50

STATIC = {
    "style.css": "text/css; charset=utf-8",
    "common.js": "text/javascript; charset=utf-8",
}


# ---------------------------------------------------------------- log

LOG = CONFIG_DIR / "lapdrop.log"
_log_lock = threading.Lock()


def log(line: str) -> None:
    """Append to %APPDATA%\\LapDrop\\lapdrop.log (kept under ~1 MB). Never raises."""
    try:
        with _log_lock:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if LOG.exists() and LOG.stat().st_size > 1_000_000:
                LOG.write_text("", encoding="utf-8")
            with open(LOG, "a", encoding="utf-8") as f:
                f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + line + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- config

class Config:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.token = ""
        self.save_dir = Path.home() / "Downloads" / APP
        self.load()

    def load(self) -> None:
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        self.token = data.get("token") or secrets.token_urlsafe(8)
        if data.get("save_dir"):
            self.save_dir = Path(data["save_dir"])
        self.chat_name = str(data.get("chat_name") or socket.gethostname())[:30]
        self.save()

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps({"token": self.token, "save_dir": str(self.save_dir),
                        "chat_name": self.chat_name}, indent=2),
            encoding="utf-8",
        )

    def set_chat_name(self, name: str) -> None:
        name = name.strip()[:30]
        if name:
            with self.lock:
                self.chat_name = name
                self.save()

    def new_token(self) -> None:
        with self.lock:
            self.token = secrets.token_urlsafe(8)
            self.save()


CONFIG = Config()


# ---------------------------------------------------------------- notes

CHAT_FILE = CONFIG_DIR / "chat.json"


class Notes:
    """The chat: messages between the laptop and every connected device.

    Kept in memory, oldest first, and saved to chat.json so the history is
    still there after a restart. `sender` identifies a device (so each page
    can tell its own messages apart); `name` is what people see.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.items: list[dict] = []
        try:
            saved = json.loads(CHAT_FILE.read_text(encoding="utf-8"))
            self.items = [m for m in saved if isinstance(m, dict) and "text" in m][-MAX_NOTES:]
        except (OSError, ValueError):
            pass
        self.next_id = max((m.get("id", 0) for m in self.items), default=0) + 1

    def _save(self) -> None:
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            CHAT_FILE.write_text(json.dumps(self.items), encoding="utf-8")
        except OSError:
            pass

    def add(self, text: str, sender: str, name: str, addr: str, host: str = "") -> None:
        """`addr` is the IP address the message really came from (not something
        the sender typed); `host` is that machine's network name when known."""
        text = text.strip()[:MAX_NOTE]
        if not text:
            return
        with self.lock:
            self.items.append({
                "id": self.next_id, "text": text, "sender": sender,
                "name": name.strip()[:30] or "Device", "addr": addr, "host": host,
                "time": time.time(),
            })
            self.next_id += 1
            del self.items[:-MAX_NOTES]
            self._save()

    def set_host(self, addr: str, host: str) -> None:
        """A name lookup finished: fill it into that device's earlier messages."""
        with self.lock:
            for m in self.items:
                if m.get("addr") == addr and m.get("sender") != "laptop" and not m.get("host"):
                    m["host"] = host
            self._save()

    def clear(self) -> None:
        with self.lock:
            self.items.clear()
            self._save()

    def snapshot(self) -> list[dict]:
        with self.lock:
            return list(self.items)


NOTES = Notes()


class HostNames:
    """Network names for the devices that chat, looked up in the background.

    A lookup can take seconds and many phones have no name to find, so it never
    holds up a message: the first message from a device shows just its IP and
    the name is filled in when (if) the lookup answers.
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.known: dict[str, str] = {}      # ip -> name ("" = looked up, none found)

    def get(self, ip: str) -> str:
        with self.lock:
            if ip in self.known:
                return self.known[ip]
            self.known[ip] = ""
        threading.Thread(target=self._lookup, args=(ip,), daemon=True).start()
        return ""

    def _lookup(self, ip: str) -> None:
        try:
            name = socket.gethostbyaddr(ip)[0]
        except OSError:
            return
        if name and name != ip:
            name = name.split(".")[0] if not name[0].isdigit() else name
            with self.lock:
                self.known[ip] = name
            NOTES.set_host(ip, name)


HOSTS = HostNames()


# ---------------------------------------------------------------- files

_BAD = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_RESERVED = {"CON", "PRN", "AUX", "NUL"} | {f"COM{i}" for i in range(1, 10)} | {f"LPT{i}" for i in range(1, 10)}
_name_lock = threading.Lock()


def safe_name(raw: str) -> str:
    """Turn whatever the sender called the file into a plain Windows file name."""
    name = raw.replace("\\", "/").split("/")[-1]
    name = _BAD.sub("_", name).strip(" .")
    if not name:
        name = "file"
    stem, ext = os.path.splitext(name)
    if stem.upper() in _RESERVED:
        stem = "_" + stem
    return stem[:150] + ext[:20]


def unique_path(folder: Path, name: str) -> Path:
    stem, ext = os.path.splitext(name)
    path = folder / name
    n = 1
    while path.exists():
        path = folder / f"{stem} ({n}){ext}"
        n += 1
    return path


def list_files(folder: Path) -> list[dict]:
    out = []
    try:
        for p in folder.iterdir():
            if p.is_file() and not p.name.endswith(".part"):
                st = p.stat()
                out.append({"name": p.name, "size": st.st_size, "time": st.st_mtime})
    except OSError:
        pass
    out.sort(key=lambda f: f["time"], reverse=True)
    return out[:LIST_LIMIT]


def find_file(folder: Path, name: str) -> Path | None:
    path = folder / safe_name(name)
    return path if path.is_file() else None


# ---------------------------------------------------------------- network

_VIRTUAL = re.compile(r"vmware|virtualbox|nordlynx|vpn|default switch|wsl|tailscale|loopback|bluetooth", re.I)
_addresses: list[dict] = []
_addr_lock = threading.Lock()


HOTSPOT_IP = "192.168.137.1"     # what Windows gives the laptop when Mobile hotspot is on
_HOTSPOT = re.compile(r"wi-fi direct virtual", re.I)

# alias | adapter description | has a default gateway (1/0) | address
_SCAN_PS = (
    "$gw = @{}; Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | "
    "ForEach-Object { $gw[\"$($_.ifIndex)\"] = 1 }; "
    "$desc = @{}; Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue | "
    "ForEach-Object { $desc[\"$($_.ifIndex)\"] = $_.InterfaceDescription }; "
    "Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.AddressState -eq 'Preferred' } | "
    "ForEach-Object { $k = \"$($_.InterfaceIndex)\"; "
    "'{0}|{1}|{2}|{3}' -f $_.InterfaceAlias, $desc[$k], [int]$gw.ContainsKey($k), $_.IPAddress }"
)


def classify(rows: list[tuple[str, str, bool, str]]) -> list[dict]:
    """(alias, description, has_gateway, ip) rows -> addresses a phone could use, best first.

    Order: real networks (with a gateway), then this laptop's own hotspot, then
    other real adapters. Virtual/VPN adapters are kept only if they have a gateway.
    """
    found = []
    for alias, desc, gateway, ip in rows:
        if ip.startswith(("127.", "169.254.")):
            continue
        hotspot = ip == HOTSPOT_IP or bool(_HOTSPOT.search(desc))
        virtual = bool(_VIRTUAL.search(alias) or _VIRTUAL.search(desc)) and not hotspot
        if virtual and not gateway:
            continue
        score = 20 if virtual else 0 if gateway else 5 if hotspot else 10
        found.append({"ip": ip, "name": "Laptop hotspot" if hotspot else alias, "hotspot": hotspot, "_s": score})
    found.sort(key=lambda a: a["_s"])
    for a in found:
        del a["_s"]
    return found


def _scan_addresses() -> list[dict]:
    rows: list[tuple[str, str, bool, str]] = []
    if os.name == "nt":
        try:
            run = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command", _SCAN_PS],
                capture_output=True, text=True, timeout=20,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            for line in run.stdout.splitlines():
                parts = line.strip().split("|")
                if len(parts) == 4 and parts[3]:
                    rows.append((parts[0], parts[1], parts[2] == "1", parts[3]))
        except (OSError, subprocess.SubprocessError):
            pass
    if not rows:
        try:
            for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
                rows.append(("", "", True, ip))
        except OSError:
            pass
    return classify(rows)


def share_url() -> str:
    """Upload address for the phone's Share menu. Uses the laptop's name, which
    stays the same on home Wi-Fi and on a hotspot (the IP address does not)."""
    return f"http://{socket.gethostname()}.local:{PORT}/d/{CONFIG.token}/api/upload"


def refresh_addresses_forever() -> None:
    global _addresses
    while True:
        found = _scan_addresses()
        with _addr_lock:
            _addresses = found
        TLS.update([a["ip"] for a in found])
        time.sleep(30)


def addresses() -> list[dict]:
    """Each address with `url` (https when available) and `plain_url` (http)."""
    with _addr_lock:
        out = []
        for a in _addresses:
            plain = f"http://{a['ip']}:{PORT}/d/{CONFIG.token}/"
            secure = f"https://{a['ip']}:{TLS_PORT}/d/{CONFIG.token}/" if TLS.ready else ""
            out.append(dict(a, url=secure or plain, plain_url=plain, secure=bool(secure)))
        return out


# ---------------------------------------------------------------- https

class Tls:
    """HTTPS on TLS_PORT with a certificate this laptop makes for itself.

    Phones that refuse plain http links ("HTTPS only" mode) need this. The
    certificate is not signed by anyone, so the phone warns once and you tap
    through. It lists the laptop's addresses and is remade when a new one
    appears.
    """

    def __init__(self) -> None:
        self.ready = False
        self.context = None
        self.server = None

    def _ensure_cert(self, ips: list[str]) -> bool:
        """Make the certificate if missing, expiring, or lacking an address. -> changed"""
        try:
            meta = json.loads(CERT_META.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            meta = {}
        have = set(meta.get("ips", []))
        fresh = meta.get("expires", 0) > time.time() + 30 * 86400
        if CERT.exists() and KEY.exists() and fresh and set(ips) <= have:
            return False

        import datetime
        import ipaddress
        from cryptography import x509
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.x509.oid import NameOID

        all_ips = sorted(have | set(ips) | {"127.0.0.1"})
        key = ec.generate_private_key(ec.SECP256R1())
        name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"{APP} on {socket.gethostname()}")])
        now = datetime.datetime.now(datetime.timezone.utc)
        expires = now + datetime.timedelta(days=365)
        san = [x509.DNSName("localhost"), x509.DNSName(socket.gethostname())]
        san += [x509.IPAddress(ipaddress.ip_address(ip)) for ip in all_ips]
        cert = (
            x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(expires)
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            .sign(key, hashes.SHA256())
        )
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        KEY.write_bytes(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ))
        CERT.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        CERT_META.write_text(json.dumps({"ips": all_ips, "expires": expires.timestamp()}), encoding="utf-8")
        return True

    def update(self, ips: list[str]) -> None:
        """Called after each address scan. Starts HTTPS once, reloads a remade certificate."""
        try:
            changed = self._ensure_cert(ips)
            if self.context is None:
                import ssl
                self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                self.context.load_cert_chain(CERT, KEY)
                self.server = DualServer(("0.0.0.0", TLS_PORT), Handler)
                self.server.context = self.context
                threading.Thread(target=self.server.serve_forever, daemon=True).start()
                self.ready = True
            elif changed:
                self.context.load_cert_chain(CERT, KEY)
        except Exception as err:   # no cryptography module, port taken...: plain http still works
            log(f"https setup problem: {type(err).__name__}: {err}")
            if self.server is None:
                self.ready = False


TLS = Tls()


# ---------------------------------------------------------------- start with Windows

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"   # per-user, no admin needed


def startup_command() -> str:
    """What Windows should run at sign-in: this app, window minimised."""
    if getattr(sys, "frozen", False):                # installed LapDrop.exe
        return f'"{sys.executable}" --minimized'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    return f'"{pythonw}" "{Path(__file__).resolve()}" --minimized'


def startup_enabled() -> bool:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP)
        return True
    except (ImportError, OSError):
        return False


def set_startup(on: bool) -> None:
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if on:
                winreg.SetValueEx(key, APP, 0, winreg.REG_SZ, startup_command())
            else:
                winreg.DeleteValue(key, APP)
    except (ImportError, OSError):
        pass


# ---------------------------------------------------------------- screen mirroring

def find_uxplay() -> Path:
    """uxplay.exe from MSYS2's default UCRT64 folder, else the first one on PATH."""
    default = Path(r"C:\msys64\ucrt64\bin\uxplay.exe")
    if default.is_file():
        return default
    found = shutil.which("uxplay")
    return Path(found) if found else default


UXPLAY = find_uxplay()
UXPLAY_LOG = CONFIG_DIR / "uxplay.log"


class Mirror:
    """Starts and stops UxPlay, a separate open-source AirPlay receiver.

    While it runs, the iPhone lists this laptop under Screen Mirroring and the
    phone's screen opens in UxPlay's own window. LapDrop only launches it; all
    the AirPlay work happens in uxplay.exe (built with MSYS2, see README).
    """

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.proc: subprocess.Popen | None = None

    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def status(self) -> dict:
        return {"available": UXPLAY.is_file(), "running": self.running(), "name": socket.gethostname()}

    def start(self) -> None:
        with self.lock:
            if self.running() or not UXPLAY.is_file():
                return
            env = dict(os.environ)
            # uxplay.exe needs the MSYS2 DLLs and GStreamer plugins that sit next to it.
            env["PATH"] = str(UXPLAY.parent) + os.pathsep + env.get("PATH", "")
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            out = open(UXPLAY_LOG, "w", encoding="utf-8", errors="replace")
            self.proc = subprocess.Popen(
                # -nh: show just the laptop's name; d3d12videosink: Alt+Enter toggles full screen
                [str(UXPLAY), "-n", socket.gethostname(), "-nh", "-vs", "d3d12videosink"],
                stdout=out, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                env=env, cwd=str(UXPLAY.parent), creationflags=subprocess.CREATE_NO_WINDOW,
            )
            out.close()
            log(f"mirroring started (pid {self.proc.pid})")

    def stop(self) -> None:
        with self.lock:
            if self.proc is None:
                return
            if self.proc.poll() is None:
                self.proc.terminate()
                try:
                    self.proc.wait(5)
                except subprocess.TimeoutExpired:
                    self.proc.kill()
            self.proc = None
            log("mirroring stopped")


MIRROR = Mirror()


# ---------------------------------------------------------------- pages

def _page(title: str, message: str) -> bytes:
    return (
        "<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'>"
        f"<title>{title}</title><link rel=stylesheet href=/static/style.css>"
        f"<main class=notice><h1>{title}</h1><p>{message}</p></main>"
    ).encode("utf-8")


EXPIRED = _page("Link not valid", "Scan the QR code on the laptop again to reconnect.")
LAPTOP_ONLY = _page("LapDrop", "Scan the QR code shown on the laptop to send files to it.")


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = APP
    sys_version = ""
    timeout = 120

    def log_message(self, fmt, *args) -> None:
        log(f"{self.client_address[0]} " + (fmt % args).replace(CONFIG.token, "<code>"))

    # ---- helpers

    def send_bytes(self, body: bytes, ctype: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if self.close_connection:
            # Tell the browser, or it reuses this connection and sees it "lost".
            self.send_header("Connection", "close")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_json(self, data, status: int = 200) -> None:
        self.send_bytes(json.dumps(data).encode("utf-8"), "application/json", status)

    def fail(self, status: int, message: str) -> None:
        self.close_connection = True      # the request body may be unread
        self.send_json({"error": message}, status)

    def send_ui(self, name: str) -> None:
        self.send_bytes((UI / name).read_bytes(), "text/html; charset=utf-8")

    def is_this_pc(self) -> bool:
        """True only for a browser on this laptop talking to localhost."""
        if self.client_address[0] not in ("127.0.0.1", "::1"):
            return False
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in ("127.0.0.1", "localhost", "[::1]")

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if not 0 < length <= 65536:
            return {}
        try:
            data = json.loads(self.rfile.read(length))
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def route(self) -> tuple[str, str, dict]:
        """-> (area, rest, query). area: 'admin', 'phone', 'static', 'root', 'denied' or ''."""
        url = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(url.query)
        path = url.path
        if path == "/":
            return "root", "", query
        if path.startswith("/static/"):
            return "static", path[8:], query
        if path.startswith("/admin/api/"):
            return ("admin" if self.is_this_pc() else "denied"), path[11:], query
        if path.startswith("/d/"):
            token, _, rest = path[3:].partition("/")
            if hmac.compare_digest(token.encode(), CONFIG.token.encode()):
                return "phone", ("/" + rest if _ or rest else ""), query
            return "denied", "", query
        return "", "", query

    def receive_file(self, folder: Path, query: dict) -> None:
        """Stream an upload to a file in `folder`.

        Two shapes are accepted:
          * the file as the whole request body, name in "?name=" (our own pages);
          * a form upload (multipart) with one file field (phone Share menu, curl -F).
        """
        try:
            remaining = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self.fail(411, "Length required")
        ctype = self.headers.get("Content-Type", "")
        boundary = None
        if ctype.lower().startswith("multipart/form-data"):
            found = re.search(r'boundary="?([^";]+)"?', ctype)
            if not found:
                return self.fail(400, "Bad form upload")
            boundary = found.group(1).encode("latin-1")
        folder.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(folder).free < remaining + 50 * CHUNK:
            return self.fail(507, "Not enough disk space on the laptop")

        def more() -> bytes:
            nonlocal remaining
            if remaining <= 0:
                return b""
            data = self.rfile.read(min(CHUNK, remaining))
            remaining -= len(data)
            return data

        name = (query.get("name") or [""])[0]
        part = folder / f".{secrets.token_hex(6)}.part"
        try:
            with open(part, "wb") as out:
                if boundary is None:
                    while remaining > 0:
                        buf = more()
                        if not buf:
                            raise ConnectionError("upload stopped early")
                        out.write(buf)
                else:
                    # Part headers, then the file bytes up to the closing boundary line.
                    buf = b""
                    while b"\r\n\r\n" not in buf:
                        data = more()
                        if not data or len(buf) > 65536:
                            raise ValueError("bad form upload")
                        buf += data
                    head, buf = buf.split(b"\r\n\r\n", 1)
                    head_text = head.decode("utf-8", "replace")
                    found = re.search(r'filename="([^"]*)"', head_text)
                    if not found:
                        raise ValueError("the form has no file")
                    name = name or found.group(1)
                    found = re.search(r"(?im)^content-type:\s*(\S+)", head_text)
                    ctype = found.group(1) if found else ""
                    end = b"\r\n--" + boundary
                    while True:
                        at = buf.find(end)
                        if at >= 0:
                            out.write(buf[:at])
                            break
                        keep = len(end) - 1          # the boundary may straddle two reads
                        out.write(buf[:-keep] if len(buf) > keep else b"")
                        buf = buf[-keep:] if len(buf) > keep else buf
                        data = more()
                        if not data:
                            raise ConnectionError("upload stopped early")
                        buf += data
                    while more():                    # anything after the file
                        pass
            if not name:    # sender gave no name: date-stamp it, guess the type
                import mimetypes
                ext = mimetypes.guess_extension(ctype.split(";")[0].strip()) or ""
                name = time.strftime("Shared %Y-%m-%d %H.%M.%S") + ext
            with _name_lock:
                final = unique_path(folder, safe_name(name))
                part.replace(final)
        except ValueError as err:
            part.unlink(missing_ok=True)
            return self.fail(400, str(err))
        except (OSError, ConnectionError):
            part.unlink(missing_ok=True)
            self.close_connection = True
            return
        self.send_json({"ok": True, "name": final.name})

    def send_download(self, path: Path) -> None:
        size = path.stat().st_size
        quoted = urllib.parse.quote(path.name)
        self.send_response(200)
        self.send_header("Content-Type", "application/octet-stream")
        self.send_header("Content-Length", str(size))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{quoted}")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        try:
            with open(path, "rb") as src:
                shutil.copyfileobj(src, self.wfile, CHUNK)
        except OSError:
            self.close_connection = True

    # ---- GET

    def do_GET(self) -> None:
        area, rest, query = self.route()
        if area == "root":
            if self.is_this_pc():
                return self.send_ui("laptop.html")
            return self.send_bytes(LAPTOP_ONLY, "text/html; charset=utf-8", 403)
        if area == "static" and rest in STATIC:
            return self.send_bytes((UI / rest).read_bytes(), STATIC[rest])
        if area == "denied":
            return self.send_bytes(EXPIRED, "text/html; charset=utf-8", 404)

        if area == "admin":
            if rest == "state":
                return self.send_json({
                    "host": socket.gethostname(),
                    "save_dir": str(CONFIG.save_dir),
                    "addresses": addresses(),
                    "mirror": MIRROR.status(),
                    "chat_name": CONFIG.chat_name,
                    "startup": startup_enabled(),
                    "received": list_files(CONFIG.save_dir),
                    "outbox": list_files(OUTBOX),
                    "notes": NOTES.snapshot(),
                })
            if rest == "qr.svg":
                ip = (query.get("ip") or [""])[0]
                match = [a for a in addresses() if a["ip"] == ip]
                if not match:
                    return self.fail(404, "Unknown address")
                import segno
                buf = io.BytesIO()
                link = match[0]["plain_url" if query.get("plain") else "url"]
                segno.make(link, error="m").save(buf, kind="svg", scale=8, border=2)
                return self.send_bytes(buf.getvalue(), "image/svg+xml")

        if area == "phone":
            if rest == "":
                self.send_response(308)
                self.send_header("Location", f"/d/{CONFIG.token}/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if rest == "/":
                return self.send_ui("phone.html")
            if rest == "/api/state":
                return self.send_json({
                    "host": socket.gethostname(),
                    "share_url": share_url(),
                    "outbox": list_files(OUTBOX),
                    "notes": NOTES.snapshot(),
                })
            if rest == "/api/file":
                path = find_file(OUTBOX, (query.get("name") or [""])[0])
                if path:
                    return self.send_download(path)

        self.fail(404, "Not found")

    do_HEAD = do_GET

    # ---- POST

    def do_POST(self) -> None:
        area, rest, query = self.route()

        if area == "phone":
            if rest == "/api/upload":
                return self.receive_file(CONFIG.save_dir, query)
            if rest == "/api/text":
                data = self.read_json()
                # "d:" prefix: a device can never pass itself off as the laptop.
                sender = "d:" + str(data.get("id") or self.client_address[0])[:40]
                ip = self.client_address[0]
                NOTES.add(str(data.get("text", "")), sender, str(data.get("name") or "Phone"),
                          ip, HOSTS.get(ip))
                return self.send_json({"ok": True})

        if area == "admin":
            # A custom header that other websites cannot send without permission.
            if self.headers.get("X-LapDrop") != "1":
                return self.fail(403, "Forbidden")
            if rest == "upload":
                return self.receive_file(OUTBOX, query)
            data = self.read_json()
            if rest == "text":
                known = addresses()
                NOTES.add(str(data.get("text", "")), "laptop", CONFIG.chat_name,
                          known[0]["ip"] if known else "127.0.0.1", socket.gethostname())
            elif rest == "name":
                CONFIG.set_chat_name(str(data.get("name", "")))
            elif rest == "startup":
                set_startup(bool(data.get("on")))
            elif rest == "clear-notes":
                NOTES.clear()
            elif rest == "new-code":
                CONFIG.new_token()
            elif rest == "mirror":
                MIRROR.start() if data.get("on") else MIRROR.stop()
            elif rest == "hotspot-settings":
                os.startfile("ms-settings:network-mobilehotspot")  # noqa: S606 - Windows Settings page
            elif rest == "remove":
                path = find_file(OUTBOX, str(data.get("name", "")))
                if path:
                    path.unlink(missing_ok=True)
            elif rest == "open":
                CONFIG.save_dir.mkdir(parents=True, exist_ok=True)
                path = find_file(CONFIG.save_dir, str(data.get("name", ""))) if data.get("name") else None
                if path:
                    subprocess.Popen(["explorer", "/select,", str(path)])
                else:
                    os.startfile(CONFIG.save_dir)  # noqa: S606 - opens our own folder
            else:
                return self.fail(404, "Not found")
            return self.send_json({"ok": True})

        if area == "denied":
            return self.fail(404, "Link not valid")
        self.fail(404, "Not found")


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def handle_error(self, request, client_address) -> None:
        # Dropped connections and refused certificates are normal; note them and carry on.
        err = sys.exc_info()[1]
        log(f"{client_address[0]} connection error: {type(err).__name__}: {err}")


class DualServer(Server):
    """Answers https and plain http on the same port.

    iPhone Safari, after you tap past its certificate warning, can fall back to
    plain http on the very same port. A TLS-only port hangs up on that and Safari
    says "the network connection was lost". So look at the first byte of each
    connection: 0x16 starts a TLS handshake, anything else is plain http.
    """

    context = None

    def finish_request(self, request, client_address) -> None:
        # Runs in the connection's own thread, so a slow phone holds up nobody else.
        request.settimeout(20)
        secure = None
        if request.recv(1, socket.MSG_PEEK) == b"\x16":
            secure = self.context.wrap_socket(request, server_side=True)
        try:
            self.RequestHandlerClass(secure or request, client_address, self)
        finally:
            if secure is not None:
                try:
                    secure.shutdown(socket.SHUT_WR)
                except OSError:
                    pass
                secure.close()


# ---------------------------------------------------------------- main

def main() -> int:
    parser = argparse.ArgumentParser(description="LapDrop - send files from a phone to this laptop")
    parser.add_argument("--browser", action="store_true", help="open in the default browser, not an app window")
    parser.add_argument("--headless", action="store_true", help="run the server without opening anything")
    parser.add_argument("--minimized", action="store_true", help="open the window minimised (used at Windows start-up)")
    args = parser.parse_args()
    local = f"http://127.0.0.1:{PORT}/"

    try:
        server = Server(("0.0.0.0", PORT), Handler)
    except OSError:
        # Most likely LapDrop is already running: just show it.
        if not args.headless:
            webbrowser.open(local)
        return 0

    CONFIG.save_dir.mkdir(parents=True, exist_ok=True)
    OUTBOX.mkdir(parents=True, exist_ok=True)
    import atexit
    atexit.register(MIRROR.stop)        # closing LapDrop also ends mirroring
    threading.Thread(target=refresh_addresses_forever, daemon=True).start()
    threading.Thread(target=server.serve_forever, daemon=True).start()
    if sys.stdout:
        print(f"{APP} is running. Laptop page: {local}", flush=True)

    if not args.headless and not args.browser:
        try:
            import webview
            webview.create_window(APP, local, width=1040, height=760, min_size=(420, 560),
                                  minimized=args.minimized)
            webview.start()
            return 0            # window closed -> quit
        except Exception:       # no pywebview / WebView2: use the browser
            args.browser = True
    if args.browser:
        webbrowser.open(local)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
