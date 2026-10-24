"""Teleportgeluid: zelf gegenereerd (of een eigen WAV-bestand) en afgespeeld via de speakers.

Het gegenereerde geluid volgt het teleport-effect: een oplopende zoem tijdens het
flikkeren en een korte "zjoep" op het moment van de flits. Bij terugkomen wordt
het achterstevoren afgespeeld, net als het effect.

Los te beluisteren:  .venv\\Scripts\\python -m itcam.sound  (maakt teleport.wav)
"""

from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44100
# Moment van de felste flits in het teleport-effect, als deel van de overgang (zie effects.py).
FLASH_AT = 0.68
FLICKER_HZ = 18.0


def _envelope(t: np.ndarray, start: float, end: float) -> np.ndarray:
    return np.clip((t - start) / (end - start), 0.0, 1.0)


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


def load_wav(path: Path) -> tuple[np.ndarray, int]:
    """Lees een 16-bit WAV-bestand als mono float32 (-1..1)."""
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2:
            raise ValueError(f"{path.name}: alleen 16-bit WAV-bestanden worden ondersteund.")
        channels = wav.getnchannels()
        rate = wav.getframerate()
        data = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16)
    data = data.reshape(-1, channels).mean(axis=1) / 32768.0
    return data.astype(np.float32), rate


def save_wav(path: Path, sound: np.ndarray, sample_rate: int = SAMPLE_RATE) -> None:
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        wav.writeframes((np.clip(sound, -1.0, 1.0) * 32767).astype(np.int16).tobytes())


class SoundPlayer:
    """Speelt het verdwijn- en terugkomgeluid af; doet niets als er geen geluid kan."""

    def __init__(self, transition_seconds: float, volume: float, path: Path | None = None) -> None:
        self.enabled = volume > 0
        self._backend = None
        if path is not None:
            try:
                sound, self._rate = load_wav(path)
            except (OSError, ValueError, wave.Error) as error:
                raise RuntimeError(f"Kan het geluidsbestand {path} niet lezen: {error}") from error
            # Een eigen geluid klinkt achterstevoren meestal vreemd: speel het beide keren gewoon af.
            self._vanish = self._appear = sound * volume
        else:
            self._rate = SAMPLE_RATE
            self._vanish = teleport_sound(transition_seconds) * volume
            self._appear = self._vanish[::-1].copy()
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
