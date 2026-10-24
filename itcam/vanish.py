"""Verdwijnen: achtergrond vastleggen, jezelf eruit knippen en de overgang.

Alleen numpy/OpenCV-rekenwerk, zodat het zonder camera of MediaPipe getest kan worden.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

# Masker iets groter maken dan de persoon, zodat randen en haar ook verdwijnen
# (relatief aan de breedte van het masker).
MASK_GROW = 0.02
MASK_FEATHER = 0.012
# Kleurverschil (0..255) t.o.v. de lege kamer vanaf waar een pixel als "jij" telt.
DIFFERENCE_THRESHOLD = 28.0
# Zo snel past de helderheid van de achtergrond zich aan de camera aan (0..1 per beeld).
BRIGHTNESS_SMOOTHING = 0.15
BRIGHTNESS_LIMITS = (0.75, 1.33)


def difference_mask(frame_small: np.ndarray, background_small: np.ndarray) -> np.ndarray:
    """Waar het beeld afwijkt van de lege kamer, ben jij (of je schaduw).

    Vangt wat het model mist, zoals kleding in dezelfde kleur als de muur.
    """
    frame_blur = cv2.GaussianBlur(frame_small, (5, 5), 0)
    background_blur = cv2.GaussianBlur(background_small, (5, 5), 0)
    distance = cv2.absdiff(frame_blur, background_blur).max(axis=2).astype(np.float32)
    mask = np.clip((distance - DIFFERENCE_THRESHOLD) / DIFFERENCE_THRESHOLD, 0.0, 1.0)
    # Losse spikkels (ruis) weghalen.
    return cv2.morphologyEx(mask, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)))


def prepare_mask(
    confidence: np.ndarray, size: tuple[int, int], difference: np.ndarray | None = None
) -> np.ndarray:
    """Maak van de ruwe MediaPipe-zekerheid (0..1) een zacht, iets vergroot masker.

    difference: optioneel verschilmasker t.o.v. de lege kamer (zelfde grootte).
    size is (breedte, hoogte) van het uitvoerbeeld.
    """
    mask = np.clip((confidence.astype(np.float32) - 0.3) / 0.4, 0.0, 1.0)
    if difference is not None:
        mask = np.maximum(mask, difference)
    width = mask.shape[1]
    grow = max(1, int(width * MASK_GROW)) | 1
    mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (grow, grow)))
    mask = cv2.GaussianBlur(mask, (0, 0), sigmaX=max(width * MASK_FEATHER, 0.5))
    return cv2.resize(mask, size, interpolation=cv2.INTER_LINEAR)


def person_fraction(confidence: np.ndarray) -> float:
    """Welk deel van het beeld een persoon is (om te controleren of je uit beeld bent)."""
    return float(np.mean(confidence > 0.5))


def hide_person(frame: np.ndarray, background: np.ndarray, mask: np.ndarray, amount: float) -> np.ndarray:
    """Vervang de persoon door de achtergrond. amount: 0 = zichtbaar, 1 = volledig weg."""
    if amount <= 0.0:
        return frame
    # In 8-bit met OpenCV: ruim 4x sneller dan met floats in numpy.
    alpha = (mask * (amount * 255.0)).astype(np.uint8)
    alpha = cv2.merge([alpha, alpha, alpha])
    keep = cv2.multiply(frame, cv2.bitwise_not(alpha), scale=1 / 255)
    return cv2.add(keep, cv2.multiply(background, alpha, scale=1 / 255))


class BrightnessMatcher:
    """Houdt de achtergrondfoto even helder als het live beeld.

    Webcams passen hun belichting steeds aan; zonder correctie zie je dan een
    lichtere of donkerdere vlek waar je zat.
    """

    def __init__(self) -> None:
        self.gain = np.ones(3, dtype=np.float32)

    def reset(self) -> None:
        self.gain = np.ones(3, dtype=np.float32)

    def update(self, frame_small: np.ndarray, background_small: np.ndarray, mask_small: np.ndarray) -> None:
        room = mask_small < 0.05
        if np.count_nonzero(room) < room.size * 0.1:
            return
        live = frame_small[room].astype(np.float32).mean(axis=0)
        stored = background_small[room].astype(np.float32).mean(axis=0)
        target = np.clip(live / np.maximum(stored, 1.0), *BRIGHTNESS_LIMITS)
        self.gain += (target - self.gain) * BRIGHTNESS_SMOOTHING

    def apply(self, background: np.ndarray) -> np.ndarray:
        if np.allclose(self.gain, 1.0, atol=0.01):
            return background
        return cv2.multiply(background, (*map(float, self.gain), 0.0))


@dataclass(frozen=True)
class CaptureStatus:
    phase: str  # "countdown", "waiting" (je bent nog in beeld) of "sampling"
    seconds_left: float


class BackgroundCapture:
    """Legt de lege kamer vast: aftellen, wachten tot je uit beeld bent, dan een
    paar beelden middelen (de mediaan haalt ruis en flikkering weg).

    Ziet het model na max_wait_seconds nog steeds een persoon (bijvoorbeeld een
    poster of tv), dan wordt de kamer toch vastgelegd.
    """

    def __init__(
        self,
        countdown_seconds: float,
        frames_needed: int = 8,
        max_person_fraction: float = 0.01,
        max_wait_seconds: float = 10.0,
    ) -> None:
        self.countdown_seconds = countdown_seconds
        self.frames_needed = frames_needed
        self.max_person_fraction = max_person_fraction
        self.max_wait_seconds = max_wait_seconds
        self._started: float | None = None
        self._frames: list[np.ndarray] = []
        self._waiting = False

    @property
    def active(self) -> bool:
        return self._started is not None

    def start(self, now: float) -> None:
        self._started = now
        self._frames = []
        self._waiting = False

    def needs_check(self, now: float) -> bool:
        """True als het volgende beeld gecontroleerd moet worden op een persoon."""
        return self._started is not None and now - self._started >= self.countdown_seconds

    def status(self, now: float) -> CaptureStatus | None:
        if self._started is None:
            return None
        left = self.countdown_seconds - (now - self._started)
        if left > 0:
            return CaptureStatus("countdown", left)
        return CaptureStatus("waiting" if self._waiting else "sampling", 0.0)

    def update(self, frame: np.ndarray, fraction: float, now: float) -> np.ndarray | None:
        """Geeft de achtergrond terug zodra die klaar is, anders None."""
        if not self.needs_check(now):
            return None
        waited = now - self._started - self.countdown_seconds
        if fraction > self.max_person_fraction and waited < self.max_wait_seconds:
            self._frames = []
            self._waiting = True
            return None
        self._waiting = False
        self._frames.append(frame.copy())
        if len(self._frames) < self.frames_needed:
            return None
        background = np.median(np.stack(self._frames), axis=0).astype(np.uint8)
        self._started = None
        self._frames = []
        return background


class Visibility:
    """Hoe zichtbaar je bent (1 = zichtbaar, 0 = weg), met een vloeiende overgang."""

    def __init__(self, transition_seconds: float) -> None:
        self.transition_seconds = transition_seconds
        self.visible = True  # waar we naartoe gaan
        self._value = 1.0
        self._last: float | None = None

    def toggle(self) -> None:
        self.visible = not self.visible

    def show_now(self) -> None:
        self.visible = True
        self._value = 1.0

    def update(self, now: float) -> float:
        """Geeft terug hoeveel van de persoon verborgen moet worden (0..1, vloeiend)."""
        elapsed = 0.0 if self._last is None else now - self._last
        self._last = now
        step = elapsed / self.transition_seconds if self.transition_seconds > 0 else 1.0
        target = 1.0 if self.visible else 0.0
        if self._value < target:
            self._value = min(target, self._value + step)
        else:
            self._value = max(target, self._value - step)
        hidden = 1.0 - self._value
        return hidden * hidden * (3.0 - 2.0 * hidden)  # smoothstep: zacht begin en einde
