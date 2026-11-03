"""Notification-area (tray) icon: show / hide the dashboard, talk, voice on/off, WhatsApp, settings, quit."""

import os
import threading

from PIL import Image, ImageDraw


def make_icon(size=64):
    """Four rounded tiles on a dark rounded square - the dashboard grid."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    s = size / 64
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=int(14 * s), fill=(21, 23, 29, 255))
    tiles = [((10, 10, 30, 54), (91, 156, 240)), ((34, 10, 54, 30), (63, 207, 90)),
             ((34, 34, 54, 54), (232, 163, 59))]
    for (x0, y0, x1, y1), color in tiles:
        d.rounded_rectangle([x0 * s, y0 * s, x1 * s, y1 * s], radius=int(5 * s), fill=color + (255,))
    return img


def ensure_ico(path):
    if not os.path.exists(path):
        make_icon(256).save(path, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (256, 256)])
    return path


class Tray:
    def __init__(self, api):
        self.api = api
        self.icon = None

    def start(self):
        import pystray
        from pystray import Menu, MenuItem as Item

        api = self.api
        voice_on = lambda item: bool(api._settings.get("voice_on"))
        menu = Menu(
            Item("Show dashboard", lambda: api._show(), default=True),     # also a left click on the icon
            Item("Hide dashboard", lambda: api._hide()),
            Menu.SEPARATOR,
            Item("Talk now  (Ctrl+Alt+Space)", lambda: api._voice and api._voice.push_to_talk()),
            Item("Listen for wake word", lambda: api.voice_toggle(not api._settings.get("voice_on")), checked=voice_on),
            Item("Speak replies", lambda: api.replies_mute(bool(api._settings.get("speak_replies"))),
                 checked=lambda item: bool(api._settings.get("speak_replies"))),
            Item("Open WhatsApp", lambda: api.whatsapp_open()),
            Item("Sign in to YouTube…", lambda: api.youtube_signin()),
            Item("Edit layout…", lambda: (api._show(), api._ui_do("edit_layout"))),
            Item("Create widget…", lambda: (api._show(), api._ui_do("widget_studio", request=""))),
            Item("Settings…", lambda: (api._show(), api._ui_do("settings"))),
            Menu.SEPARATOR,
            Item("Quit dashboard", lambda: api._quit()),
        )
        self.icon = pystray.Icon("Dashboard", make_icon(64), "Sekar's Dashboard  (Ctrl+Alt+D to show)", menu)
        threading.Thread(target=self.icon.run, daemon=True).start()

    def stop(self):
        if self.icon is not None:
            self.icon.stop()
