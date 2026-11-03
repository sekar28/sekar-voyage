"""The timer / reminder bell: a synthesized two-tone chime that keeps ringing until it is acknowledged.

It plays through sounddevice, separately from the spoken replies (winsound), so saying the label never cuts the
bell's state and vice versa."""

import threading
import time

RATE = 48000
MIN_RING = 5.0          # always ring at least this long (unless stopped by hand)
MAX_RING = 120.0        # then give up ringing; the widget keeps flashing until acknowledged


def bell_wave():
    """~2 s loop: two bell strikes (with overtones and a fast decay), then a short gap."""
    import numpy as np
    t = np.arange(int(RATE * 0.9)) / RATE

    def strike(f):
        tone = sum(a * np.sin(2 * np.pi * f * m * t) for m, a in ((1, 1.0), (2.76, 0.45), (5.4, 0.2), (8.9, 0.08)))
        return tone * np.exp(-t * 4.5) * np.minimum(1, t * 400)      # quick attack, ring-out
    loop = np.concatenate([strike(988), strike(784)[: int(RATE * 0.75)], np.zeros(int(RATE * 0.35))])
    return (loop / np.abs(loop).max() * 0.6).astype(np.float32)


class Bell:
    def __init__(self):
        self._stop = threading.Event()
        self._thread = None
        self._wave = None

    @property
    def ringing(self):
        return self._thread is not None and self._thread.is_alive()

    def ring(self, say=None):
        """Start ringing (no-op if already ringing). say(): speaks the label after the first MIN_RING seconds."""
        if self.ringing:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, args=(say,), daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def chime(self):
        """One bell strike pair (~2 s), for critical PC alerts. Blocks until played; skipped while a timer rings."""
        if self.ringing:
            return
        try:
            import sounddevice as sd
            if self._wave is None:
                self._wave = bell_wave()
            sd.play(self._wave, RATE)
            sd.wait()
        except Exception:
            import winsound
            winsound.Beep(988, 250)
            winsound.Beep(784, 350)

    def _play(self, seconds):
        """Ring for up to `seconds`, returning early if stopped."""
        try:
            import sounddevice as sd
            if self._wave is None:
                self._wave = bell_wave()
            sd.play(self._wave, RATE, loop=True)
            self._stop.wait(seconds)
            sd.stop()
        except Exception:                     # no sounddevice / audio device busy: fall back to the system beep
            import winsound
            end = time.time() + seconds
            while time.time() < end and not self._stop.is_set():
                winsound.Beep(988, 250)
                winsound.Beep(784, 350)
                self._stop.wait(0.4)

    def _run(self, say):
        start = time.time()
        self._play(MIN_RING)
        if self._stop.is_set():
            return
        if say:
            say()                             # blocks until the label has been spoken
        while not self._stop.is_set() and time.time() - start < MAX_RING:
            self._play(min(10.0, MAX_RING - (time.time() - start)))
