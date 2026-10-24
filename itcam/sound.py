"""Teleportgeluid via de speakers: een eigen geluidsbestand of het ingebouwde geluid.

Een eigen bestand (bijvoorbeeld sounds/teleport.mp3) wordt bijgeknipt en zo
verschoven dat de klap samenvalt met de flits in het beeld.

Het ingebouwde geluid volgt het teleport-effect: een oplopende zoem tijdens het
flikkeren en een korte "zjoep" op het moment van de flits. Bij terugkomen wordt
het achterstevoren afgespeeld, net als het effect.

Los te beluisteren:  .venv\\Scripts\\python -m itcam.sound  (maakt teleport.wav)
"""

from __future__ import annotations

import sys
import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44100
# Moment van de felste flits in het teleport-effect, als deel van de overgang (zie effects.py).
FLASH_AT = 0.68
FLICKER_HZ = 18.0
# Map voor je eigen geluid. Staat naast het programma; wordt nooit naar GitHub gestuurd.
SOUNDS_DIR = (
    Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
) / "sounds"
SOUND_EXTENSIONS = (".mp3", ".wav", ".ogg", ".flac")
SILENCE_LEVEL = 0.02


def teleport_sound(duration: float, sample_rate: int = SAMPLE_RATE) -> np.ndarray:
    """Genereer het verdwijngeluid (mono, float32, -1..1) voor een overgang van duration seconden."""
    rng = np.random.default_rng(7)
    length = int(duration * sample_rate)
    t = np.arange(length, dtype=np.float32) / sample_rate
    flash = FLASH_AT * duration

    # 1. Oplopende, trillende zoem tot aan de flits (exponentiële toonhoogte 250 -> 2000 Hz).
    build = np.clip(t / flash, 0.0, 1.0)
    frequency = 250.0 * (8.0 ** build)
    phase = 2 * np.pi * np.cumsum(frequency) / sample_rate
    tremolo = 0.65 + 0.35 * np.sin(2 * np.pi * FLICKER_HZ * t)
    hum = (np.sin(phase) + 0.5 * np.sin(2 * phase) + 0.25 * np.sin(3.01 * phase)) / 1.75
    hum *= build**2 * tremolo * (t < flash)

    # 2. Ruis die aanzwelt (een 'whoosh'), hoog-doorgelaten zodat het sist in plaats van bromt.
    noise = rng.standard_normal(length).astype(np.float32)
    noise = noise - np.convolve(noise, np.ones(8) / 8, mode="same")
    whoosh = noise * 0.35 * build**3 * (t < flash)

    # 3. De 'zjoep' bij de flits: snel dalende toon met een tik, daarna kort naklinken.
    after = np.clip(t - flash, 0.0, None)
    zip_frequency = 200.0 + 2800.0 * np.exp(-after / 0.025)
    zip_phase = 2 * np.pi * np.cumsum(zip_frequency) / sample_rate
    zip_tone = np.sin(zip_phase) * np.exp(-after / 0.09) * (t >= flash)
    click = noise * np.exp(-after / 0.006) * (t >= flash) * 0.8

    sound = 0.45 * hum + whoosh + 0.9 * zip_tone + click
    # Zachte randen zodat er geen klik aan begin en eind zit.
    fade = int(0.01 * sample_rate)
    sound[:fade] *= np.linspace(0.0, 1.0, fade)
    sound[-fade:] *= np.linspace(1.0, 0.0, fade)
    return (sound / max(float(np.abs(sound).max()), 1e-6) * 0.9).astype(np.float32)


def load_sound(path: Path) -> tuple[np.ndarray, int]:
    """Lees een geluidsbestand (MP3, WAV, OGG of FLAC) als mono float32 (-1..1)."""
    import soundfile

    data, rate = soundfile.read(str(path), dtype="float32", always_2d=True)
    return data.mean(axis=1), rate


def find_custom_sound(directory: Path | None = None) -> Path | None:
    """Zoek sounds/teleport.mp3 (of .wav, .ogg, .flac)."""
    directory = directory or SOUNDS_DIR
    for extension in SOUND_EXTENSIONS:
        path = directory / f"teleport{extension}"
        if path.is_file():
            return path
    return None


def trim_silence(sound: np.ndarray) -> np.ndarray:
    """Knip stilte aan begin en eind weg."""
    loud = np.flatnonzero(np.abs(sound) > SILENCE_LEVEL * max(float(np.abs(sound).max()), 1e-6))
    if loud.size == 0:
        return sound
    return sound[loud[0]:loud[-1] + 1]


def peak_time(sound: np.ndarray, sample_rate: int) -> float:
    """Moment (s) waarop het geluid het hardst is, over blokjes van 20 ms."""
    block = max(1, int(0.02 * sample_rate))
    usable = len(sound) // block * block
    if usable == 0:
        return 0.0
    loudness = np.sqrt(np.mean(sound[:usable].reshape(-1, block) ** 2, axis=1))
    return (int(loudness.argmax()) + 0.5) * block / sample_rate


def align_peak(sound: np.ndarray, sample_rate: int, at_seconds: float) -> np.ndarray:
    """Laat het geluid later beginnen zodat de klap op at_seconds valt (nooit eerder dan nu)."""
    delay = int(round((at_seconds - peak_time(sound, sample_rate)) * sample_rate))
    if delay <= 0:
        return sound
    return np.concatenate([np.zeros(delay, dtype=sound.dtype), sound])


def prepare_custom_sound(sound: np.ndarray, sample_rate: int, transition_seconds: float) -> tuple[np.ndarray, np.ndarray]:
    """Maak van een eigen geluid een verdwijn- en terugkomversie, afgestemd op de flits."""
    sound = trim_silence(sound)
    sound = sound / max(float(np.abs(sound).max()), 1e-6) * 0.9
    # Een eigen geluid klinkt achterstevoren meestal vreemd: beide keren vooruit afspelen.
    vanish = align_peak(sound, sample_rate, FLASH_AT * transition_seconds)
    appear = align_peak(sound, sample_rate, (1.0 - FLASH_AT) * transition_seconds)
    return vanish.astype(np.float32), appear.astype(np.float32)


def save_wav(path: Path, sound: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes((np.clip(sound, -1.0, 1.0) * 32767).astype(np.int16).tobytes())


class SoundPlayer:
    """Speelt het verdwijn- en terugkomgeluid af; doet niets als er geen geluid kan."""

    def __init__(self, transition_seconds: float, volume: float, path: Path | None = None) -> None:
        """path: eigen geluid; zonder path wordt sounds/teleport.* gebruikt als dat bestaat."""
        self.enabled = volume > 0
        self._backend = None
        path = path or find_custom_sound()
        if path is not None:
            try:
                sound, self._rate = load_sound(path)
            except Exception as error:
                raise RuntimeError(f"Kan het geluidsbestand {path} niet lezen: {error}") from error
            vanish, appear = prepare_custom_sound(sound, self._rate, transition_seconds)
            self.description = f"eigen geluid {path.name}"
        else:
            self._rate = SAMPLE_RATE
            vanish = teleport_sound(transition_seconds)
            appear = vanish[::-1].copy()
            self.description = "ingebouwd teleportgeluid"
        self._vanish, self._appear = vanish * volume, appear * volume
        if not self.enabled:
            return
        try:
            import sounddevice

            sounddevice.check_output_settings(samplerate=self._rate, channels=1)
            self._backend = sounddevice
        except Exception as error:
            print(f"[Geluid] Geen geluid mogelijk ({error}). Het programma werkt verder zonder geluid.")
            self.enabled = False

    def _play(self, sound: np.ndarray) -> None:
        if not self.enabled or self._backend is None:
            return
        try:
            self._backend.play(sound, self._rate)  # speelt af op de achtergrond
        except Exception as error:
            print(f"[Geluid] Afspelen mislukt: {error}")

    def play_vanish(self) -> None:
        self._play(self._vanish)

    def play_appear(self) -> None:
        self._play(self._appear)

    def toggle(self) -> bool:
        """Zet het geluid aan of uit; geeft de nieuwe stand terug."""
        if self._backend is not None:
            self.enabled = not self.enabled
        return self.enabled


if __name__ == "__main__":
    output = Path("teleport.wav")
    save_wav(output, teleport_sound(0.8))
    print(f"Opgeslagen: {output.resolve()}")
