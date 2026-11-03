"""Microphone loop: wake word (openWakeWord, on this PC) -> record until you stop talking -> speech-to-text.
Shared by the Dashboard and System Utilities. Each app sets its own VOCAB (see its voice.py alias).

Speech-to-text uses a cloud service - Google Gemini (audio sent to its chat endpoint) or any OpenAI-style
/audio/transcriptions endpoint (OpenAI, Groq...) - and falls back to faster-whisper on this PC when there's no key,
no internet, or the service is busy. With wake=False only push-to-talk starts a recording (used while another app
is the one listening for the wake word)."""

import base64
import ctypes
import io
import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid
import wave
import winsound
from ctypes import wintypes

RATE = 16000
FRAME = 1280                 # 80 ms - the chunk size openWakeWord expects
WAKE_THRESHOLD = 0.5
DEFAULT_PAUSE = 1.6          # seconds of quiet that end a request (setting: stt_pause)
NO_SPEECH_GIVE_UP = 6.0      # after the wake word, how long to wait for you to start talking
MAX_RECORD = 25.0
MIN_THRESHOLD = 60.0         # RMS level counted as speech, at least (a headset mic idles around 10); raised in noisy rooms
WAKE_WORDS = {"hey_jarvis": "Hey Jarvis", "alexa": "Alexa", "hey_mycroft": "Hey Mycroft", "hey_rhasspy": "Hey Rhasspy"}
GEMINI_MODEL = "gemini-flash-lite-latest"
STT_PRESETS = [
    {"name": "Google Gemini", "base": "https://generativelanguage.googleapis.com/v1beta/openai", "model": GEMINI_MODEL},
    {"name": "OpenAI", "base": "https://api.openai.com/v1", "model": "gpt-4o-transcribe"},
    {"name": "Groq (fast, cheap)", "base": "https://api.groq.com/openai/v1", "model": "whisper-large-v3-turbo"},
]
# Local Whisper sizes, most accurate last. "auto" = Large v3 Turbo on an NVIDIA GPU, Small on the CPU.
WHISPER_MODELS = {"auto": "Automatic (Large v3 Turbo on GPU, Small on CPU)", "base.en": "Base (fastest, least accurate)",
                  "small.en": "Small", "medium.en": "Medium (slower, more accurate)",
                  "large-v3-turbo": "Large v3 Turbo (most accurate; slow without a GPU)"}
WHISPER_DEVICES = {"auto": "GPU if available, else CPU", "cuda": "NVIDIA GPU", "cpu": "CPU"}
STT_MODES = {"cloud": "Cloud first, local Whisper if it fails", "local_first": "Local Whisper first, cloud if it fails",
             "local": "Local Whisper only"}
# Words the app expects; given to Whisper / Gemini so they spell them right. Each app overrides this after import.
VOCAB = "Voice commands for a voice-controlled assistant."


def missing_packages():
    import importlib.util
    return [pkg for mod, pkg in (("numpy", "numpy"), ("sounddevice", "sounddevice"), ("openwakeword", "openwakeword"))
            if importlib.util.find_spec(mod) is None]


def to_wav(pcm):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm)
    return buf.getvalue()


def is_gemini(base):
    return "generativelanguage.googleapis.com" in (base or "")


def gemini_stt(pcm, base, model, key, timeout=30):
    """Gemini has no /audio/transcriptions; its OpenAI-style chat endpoint accepts audio instead."""
    if not model.startswith("gemini"):
        model = GEMINI_MODEL
    payload = {"model": model, "temperature": 0, "messages": [{"role": "user", "content": [
        {"type": "text", "text": "Transcribe this spoken request to a voice-controlled dashboard, word for word. "
                                 f"{VOCAB} Reply with the transcript only - no quotes, no notes. "
                                 "If there is no speech, reply with nothing."},
        {"type": "input_audio", "input_audio": {"data": base64.b64encode(to_wav(pcm)).decode(), "format": "wav"}}]}]}
    req = urllib.request.Request(base.rstrip("/") + "/chat/completions", data=json.dumps(payload).encode(),
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            reply = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Gemini speech-to-text returned HTTP {e.code}") from e
    text = ((reply.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return text.strip().strip('"').strip()


def cloud_stt(pcm, base, model, key, timeout=30):
    if is_gemini(base):
        return gemini_stt(pcm, base, model, key, timeout)
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="model"\r\n\r\n{model}\r\n'.encode(),
             f'--{boundary}\r\nContent-Disposition: form-data; name="language"\r\n\r\nen\r\n'.encode(),
             f'--{boundary}\r\nContent-Disposition: form-data; name="prompt"\r\n\r\n{VOCAB}\r\n'.encode(),
             f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="speech.wav"\r\n'
             f'Content-Type: audio/wav\r\n\r\n'.encode() + to_wav(pcm) + b"\r\n",
             f"--{boundary}--\r\n".encode()]
    req = urllib.request.Request(base.rstrip("/") + "/audio/transcriptions", data=b"".join(parts), headers={
        "Authorization": f"Bearer {key}", "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8")).get("text", "").strip()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Speech-to-text returned HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:200]}") from e


_cuda_paths_added = False


def add_cuda_paths():
    """faster-whisper finds cuBLAS / cuDNN from the nvidia-*-cu12 pip packages only if their bin folders are on
    the DLL search path."""
    global _cuda_paths_added
    if _cuda_paths_added:
        return
    import glob
    import site
    roots = site.getsitepackages() + [site.getusersitepackages()]
    for d in {d for r in roots for d in glob.glob(os.path.join(r, "nvidia", "*", "bin"))}:
        os.add_dll_directory(d)
        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
    _cuda_paths_added = True


class LocalWhisper:
    def __init__(self, size="auto", device="auto"):
        self.size_pref = size if size in WHISPER_MODELS else "auto"
        self.device_pref = device if device in WHISPER_DEVICES else "auto"
        self.size = None               # what actually loaded
        self.device = None
        self.note = ""                 # why the GPU wasn't used, if it wasn't
        self._model = None
        self._lock = threading.Lock()

    def matches(self, size, device):
        return (size or "auto", device or "auto") == (self.size_pref, self.device_pref)

    def available(self):
        # find_spec only checks it's installed; importing faster_whisper takes seconds and stalled startup
        import importlib.util
        return importlib.util.find_spec("faster_whisper") is not None

    def status(self):
        if self._model is None:
            return "not loaded yet"
        return f"{self.size} on {'GPU' if self.device == 'cuda' else 'CPU'}" + (f" ({self.note})" if self.note else "")

    def load(self):
        with self._lock:
            if self._model is not None:
                return
            import numpy as np
            from faster_whisper import WhisperModel
            warm = np.zeros(RATE, dtype=np.float32)
            if self.device_pref in ("auto", "cuda"):
                try:
                    import ctranslate2
                    add_cuda_paths()
                    if ctranslate2.get_cuda_device_count() < 1:
                        raise RuntimeError("no NVIDIA GPU found")
                    size = "large-v3-turbo" if self.size_pref == "auto" else self.size_pref
                    model = WhisperModel(size, device="cuda", compute_type="int8_float16")
                    list(model.transcribe(warm, language="en", vad_filter=False)[0])   # loads cuDNN now, not mid-request
                    self._model, self.size, self.device = model, size, "cuda"
                    return
                except Exception as e:
                    self.note = f"GPU not used: {str(e)[:120]}"
            size = "small.en" if self.size_pref == "auto" else self.size_pref
            self._model = WhisperModel(size, device="cpu", compute_type="int8")
            self.size, self.device = size, "cpu"

    def transcribe(self, pcm):
        import numpy as np
        self.load()
        audio = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if 0.0 < peak < 0.5:                 # quiet mics: bring speech up to a level Whisper handles well
            audio = audio * (0.7 / peak)
        segments, _ = self._model.transcribe(audio, language="en", beam_size=5, vad_filter=True,
                                             initial_prompt=VOCAB, condition_on_previous_text=False)
        return " ".join(s.text for s in segments).strip()


class Hotkeys(threading.Thread):
    """Global Ctrl+Alt+<key> shortcuts via RegisterHotKey (no keyboard hook, no extra package).
    keys: {virtual-key code: callback}, e.g. {0x20: talk} for Ctrl+Alt+Space."""
    MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY = 0x1, 0x2, 0x4000, 0x312

    def __init__(self, keys):
        super().__init__(daemon=True)
        self.keys = keys

    def run(self):
        user32 = ctypes.windll.user32
        ids = {}
        for i, (vk, callback) in enumerate(self.keys.items(), 1):
            if user32.RegisterHotKey(None, i, self.MOD_CONTROL | self.MOD_ALT | self.MOD_NOREPEAT, vk):
                ids[i] = callback
        msg = wintypes.MSG()
        while ids and user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == self.WM_HOTKEY and msg.wParam in ids:
                threading.Thread(target=ids[msg.wParam], daemon=True).start()


class VoiceLoop(threading.Thread):
    """states reported through on_state: off, starting, listening, recording, transcribing, error"""

    def __init__(self, settings, get_stt_key, on_state, on_text, is_speaking, last_wav=None, wake=True):
        super().__init__(daemon=True)
        self.wake = wake                  # False: push-to-talk only, no wake word model
        self.settings = settings          # callable -> current settings dict
        self.get_stt_key = get_stt_key
        self.on_state = on_state
        self.on_text = on_text
        self.is_speaking = is_speaking
        self.last_wav = last_wav          # the latest request is saved here, to hear what the mic picked up
        self.local = LocalWhisper(settings().get("whisper_model"), settings().get("whisper_device"))
        self._halt = threading.Event()    # not "_stop": that would hide Thread._stop and break join()
        self._ptt = threading.Event()
        self.state = "off"

    def _set(self, state, detail=None):
        self.state = state
        self.on_state(state, detail)

    def stop(self):
        self._halt.set()

    def push_to_talk(self):
        self._ptt.set()

    def transcribe(self, pcm):
        s = self.settings()
        key = self.get_stt_key()
        if not self.local.matches(s.get("whisper_model"), s.get("whisper_device")):
            self.local = LocalWhisper(s.get("whisper_model"), s.get("whisper_device"))
        mode = s.get("stt_mode") or "cloud"
        local_ok = self.local.available()
        if mode == "local_first" and local_ok:
            try:
                return self.local.transcribe(pcm), f"local {self.local.size}"
            except Exception as e:
                if not key:
                    raise RuntimeError(f"Local Whisper failed: {e}") from e
        if mode != "local" and key:
            try:
                return cloud_stt(pcm, s["stt_base"], s["stt_model"], key), "cloud"
            except (OSError, RuntimeError) as e:
                if not local_ok or mode == "local_first":
                    raise RuntimeError(f"{e} (and local Whisper isn't available)") from e
        if not local_ok:
            raise RuntimeError("No speech-to-text: add a key in Settings or install faster-whisper.")
        return self.local.transcribe(pcm), f"local {self.local.size}"

    def run(self):
        missing = [p for p in missing_packages() if self.wake or p != "openwakeword"]
        if missing:
            return self._set("error", "Voice needs: pip install " + " ".join(missing))
        self._set("starting", "Loading the wake word model…" if self.wake else "Opening the microphone…")
        word = self.settings().get("wake_word") or "hey_jarvis"
        try:
            import numpy as np
            import sounddevice as sd
            model = None
            if self.wake:
                from openwakeword import utils as oww_utils
                from openwakeword.model import Model
                try:
                    oww_utils.download_models(model_names=[word])
                except Exception:
                    pass                  # already downloaded, or offline with a cached copy
                model = Model(wakeword_models=[word], inference_framework="onnx")
        except Exception as e:
            return self._set("error", f"Wake word model failed to load: {e}")
        idle = WAKE_WORDS.get(word, word) if self.wake else "push-to-talk"

        try:
            stream = sd.InputStream(samplerate=RATE, channels=1, dtype="int16", blocksize=FRAME)
            stream.start()
        except Exception as e:
            return self._set("error", f"Can't open the microphone: {e}")

        if self.settings().get("stt_mode") in ("local", "local_first") and self.local.available():
            # load Whisper now rather than on the first request (it takes several seconds)
            threading.Thread(target=self.local.load, daemon=True).start()
        noise = 80.0                      # background level; adapts within a few seconds
        self._set("listening", idle)
        try:
            while not self._halt.is_set():
                frame, _ = stream.read(FRAME)
                samples = frame[:, 0]
                if self.is_speaking():           # don't wake up on our own voice
                    if model is not None:
                        model.reset()
                    continue
                rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
                noise = noise * 0.98 + rms * 0.02 if rms < noise * 3 else noise
                triggered = self._ptt.is_set()
                if not triggered and model is not None:
                    scores = model.predict(samples)
                    triggered = max(scores.values(), default=0) >= WAKE_THRESHOLD
                if not triggered:
                    continue
                self._ptt.clear()
                if model is not None:
                    model.reset()
                pcm = self._record(stream, np, max(MIN_THRESHOLD, noise * 4.0))
                if pcm is None:
                    self._set("listening", idle)
                    continue
                if self.last_wav:
                    try:
                        with open(self.last_wav, "wb") as f:
                            f.write(to_wav(pcm))
                    except OSError:
                        pass
                self._set("transcribing")
                try:
                    text, how = self.transcribe(pcm)
                except Exception as e:
                    self._set("error", str(e))
                    time.sleep(2)
                    self._set("listening", idle)
                    continue
                self._set("listening", idle)
                if text:
                    self.on_text(text, how)
        finally:
            stream.stop()
            stream.close()
            self._set("off")

    def _record(self, stream, np, threshold):
        """Record until you've paused for stt_pause seconds. Once you've started talking, softer sounds
        (trailing words, breaths between words) still count as speech, so a short gap doesn't cut you off."""
        self._set("recording")
        threading.Thread(target=winsound.Beep, args=(880, 90), daemon=True).start()   # "go ahead" chime
        pause = float(self.settings().get("stt_pause") or DEFAULT_PAUSE)
        chunks, spoke, quiet, elapsed = [], False, 0.0, 0.0
        step = FRAME / RATE
        while not self._halt.is_set():
            frame, _ = stream.read(FRAME)
            chunks.append(frame[:, 0].tobytes())
            elapsed += step
            if elapsed < 0.25:                # skip the chime
                continue
            rms = float(np.sqrt(np.mean(frame[:, 0].astype(np.float32) ** 2)))
            if rms > (threshold * 0.6 if spoke else threshold):
                spoke, quiet = True, 0.0
            else:
                quiet += step
            if (spoke and quiet >= pause) or elapsed >= MAX_RECORD:
                break
            if not spoke and elapsed >= NO_SPEECH_GIVE_UP:
                return None
        return b"".join(chunks) if spoke else None
