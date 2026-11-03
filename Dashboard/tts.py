"""Spoken replies. Piper (local neural voice) when installed, otherwise the built-in Windows voice."""

import os
import re
import subprocess
import tempfile
import threading
import urllib.request
import wave
import winsound

VOICES_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main/{lang}/{code}/{name}/{quality}/{voice}"
DEFAULT_VOICE = "en_US-libritts_r-medium"   # trained on LibriTTS-R, CC BY 4.0 (lessac is research-only data)
NO_WINDOW = 0x08000000


def _voice_files(voice):
    """en_US-lessac-medium -> download URLs for the .onnx model and its .json config."""
    code, name, quality = voice.split("-", 2)
    base = VOICES_URL.format(lang=code.split("_")[0], code=code, name=name, quality=quality, voice=voice)
    return base + ".onnx", base + ".onnx.json"


def clean(text):
    """What a voice should read: no markdown, no URLs."""
    text = re.sub(r"https?://\S+", "", text or "")
    text = re.sub(r"[*_#`>|]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


class Speaker:
    def __init__(self, voices_dir, voice=DEFAULT_VOICE):
        self.voices_dir = voices_dir
        self.voice_name = voice or DEFAULT_VOICE
        self._piper = None
        self._piper_error = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._proc = None                 # Windows-voice fallback process, so stop() can end it
        self.speaking = False

    def stop(self):
        """Cut off the current reply (and any queued ones)."""
        self._stop.set()
        winsound.PlaySound(None, 0)
        proc = self._proc
        if proc is not None and proc.poll() is None:
            proc.kill()

    @property
    def engine(self):
        try:
            import piper  # noqa: F401
            return "Piper"
        except ImportError:
            return "Windows voice"

    def _load_piper(self):
        if self._piper is not None or self._piper_error:
            return self._piper
        try:
            from piper import PiperVoice
        except ImportError:
            self._piper_error = "not installed"
            return None
        model = os.path.join(self.voices_dir, self.voice_name + ".onnx")
        try:
            if not os.path.exists(model) or not os.path.exists(model + ".json"):
                os.makedirs(self.voices_dir, exist_ok=True)
                for url, dest in zip(_voice_files(self.voice_name), (model, model + ".json")):
                    urllib.request.urlretrieve(url, dest + ".part")
                    os.replace(dest + ".part", dest)
            self._piper = PiperVoice.load(model)
        except Exception as e:
            self._piper_error = str(e)
        return self._piper

    def _piper_wav(self, voice, text, path):
        with wave.open(path, "wb") as wav:
            if hasattr(voice, "synthesize_wav"):          # piper-tts 1.3+
                voice.synthesize_wav(text, wav)
            else:                                          # piper-tts 1.2
                voice.synthesize(text, wav)
        self._clean_wav(path)

    @staticmethod
    def _clean_wav(path):
        """Piper normalises speech to full scale at 22.05 kHz. Windows then resamples it to the device's 48 kHz,
        and full-scale peaks overshoot in the resampler - heard as crackle / static on loud syllables. So: leave
        headroom (peak -3 dB) and resample to 48 kHz here, cleanly, before Windows touches it."""
        try:
            import numpy as np
        except ImportError:
            return
        with wave.open(path) as w:
            rate, ch = w.getframerate(), w.getnchannels()
            a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float64)
        if ch != 1 or not a.size:
            return
        out_rate = 48000
        pad = 1024                                   # silence at both ends keeps the FFT resample from wrapping
        a = np.concatenate([np.zeros(pad), a, np.zeros(pad)])
        n_out = int(round(len(a) * out_rate / rate))
        spec = np.fft.rfft(a)
        b = np.fft.irfft(spec, n_out) * (n_out / len(a))
        trim = int(round(pad * out_rate / rate))
        b = b[trim:len(b) - trim]
        peak = np.abs(b).max() or 1.0
        b = b * (0.7 * 32767 / peak)                 # about -3 dB
        with wave.open(path, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(out_rate)
            w.writeframes(np.clip(b, -32767, 32767).astype(np.int16).tobytes())

    def _windows_voice(self, text):
        script = ("Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                  "$s.Rate = 1; $s.Speak([Console]::In.ReadToEnd())")
        self._proc = subprocess.Popen(["powershell", "-NoProfile", "-Command", script], stdin=subprocess.PIPE,
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True,
                                      creationflags=NO_WINDOW)
        try:
            self._proc.communicate(text, timeout=120)
        finally:
            self._proc = None

    def _play(self, path):
        """Play a WAV without blocking winsound, so stop() can cut it off."""
        with wave.open(path) as w:
            seconds = w.getnframes() / w.getframerate()
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        self._stop.wait(seconds + 0.15)

    def say_and_wait(self, text, timeout=60):
        done = threading.Event()
        self.say(text, on_end=done.set)
        done.wait(timeout)

    def say(self, text, on_start=None, on_end=None):
        """Speak in the background; a new reply waits for the current one."""
        text = clean(text)
        if not text:
            return
        self._stop.clear()
        threading.Thread(target=self._say, args=(text, on_start, on_end), daemon=True).start()

    def _say(self, text, on_start, on_end):
        with self._lock:
            if self._stop.is_set():
                if on_end:
                    on_end()
                return
            self.speaking = True
            if on_start:
                on_start()
            try:
                voice = self._load_piper()
                if voice is not None:
                    fd, path = tempfile.mkstemp(suffix=".wav")
                    os.close(fd)
                    try:
                        self._piper_wav(voice, text, path)
                        if not self._stop.is_set():
                            self._play(path)
                    finally:
                        winsound.PlaySound(None, 0)    # release the file before deleting it
                        os.remove(path)
                else:
                    self._windows_voice(text)
            except Exception:
                if not self._stop.is_set():
                    try:
                        self._windows_voice(text)
                    except Exception:
                        pass
            finally:
                self.speaking = False
                if on_end:
                    on_end()
