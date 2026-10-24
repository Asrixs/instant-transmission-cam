"""Overgangseffecten voor verdwijnen en terugkomen.

Elk effect krijgt de voortgang van de overgang (0 = zichtbaar, 1 = weg). Bij
terugkomen loopt die van 1 naar 0, zodat het effect achterstevoren speelt.
Effecten veranderen alleen pixels binnen het masker: de rest van de kamer
blijft het live beeld.
"""

from __future__ import annotations

import cv2
import numpy as np

from .vanish import hide_person

# Kleur van lijnen en flits (BGR): wit met een vleugje blauw, zoals in de anime.
GLOW_COLOR = (255, 238, 200)


def smoothstep(value: float) -> float:
    value = min(max(value, 0.0), 1.0)
    return value * value * (3.0 - 2.0 * value)


def ramp(value: float, start: float, end: float) -> float:
    """0 voor start, 1 na end, lineair daartussen."""
    return min(max((value - start) / (end - start), 0.0), 1.0)


def random_for_slot(slot: int, salt: int = 0) -> float:
    """Herhaalbaar 'willekeurig' getal 0..1 per tijdvak, zonder globale toestand."""
    value = (slot * 2654435761 + salt * 40503 + 12345) % 2**32
    value = (value ^ (value >> 15)) * 2246822519 % 2**32
    return (value ^ (value >> 13)) / 2**32


def add_glow(image: np.ndarray, intensity: np.ndarray, color: tuple[int, int, int] = GLOW_COLOR) -> np.ndarray:
    """Tel licht op bij het beeld. intensity: 0..1 per pixel."""
    alpha = (np.clip(intensity, 0.0, 1.0) * 255).astype(np.uint8)
    glow = cv2.merge([cv2.multiply(alpha, color[c] / 255.0) for c in range(3)])
    return cv2.add(image, glow)


class FadeEffect:
    """Zachte vervaging."""

    name = "fade"

    def render(self, frame, background, mask, hidden: float, now: float) -> np.ndarray:
        return hide_person(frame, background, mask, smoothstep(hidden))


class TeleportEffect:
    """Instant Transmission: flikkeren, verticale snelheidslijnen, een flits en weg.

    Verloop van de overgang (verdwijnen; terugkomen is precies andersom):
      0.00-0.15  snelheidslijnen komen op
      0.15-0.65  je flikkert, steeds vaker weg
      0.65-0.80  witte flits op je silhouet, daarna ben je weg
      0.80-1.00  laatste lijnen vervagen
    """

    name = "teleport"
    FLICKER_HZ = 18.0
    LINE_SPEED = 1.6  # beeldhoogtes per seconde

    def __init__(self) -> None:
        self._streaks: np.ndarray | None = None

    def _streak_texture(self, height: int, width: int) -> np.ndarray:
        """Verticale strepen, twee keer zo hoog als het beeld zodat ze kunnen 'scrollen'."""
        if self._streaks is None or self._streaks.shape[1] != width or self._streaks.shape[0] != 2 * height:
            rng = np.random.default_rng(17)
            columns = max(8, width // 6)
            rows = 24
            texture = rng.random((rows, columns), dtype=np.float32)
            texture = np.clip((texture - 0.72) / 0.28, 0.0, 1.0)  # alleen de sterkste worden lijnen
            texture = cv2.resize(texture, (width, height), interpolation=cv2.INTER_LINEAR)
            texture = np.vstack([texture, texture])
            self._streaks = cv2.GaussianBlur(texture, (0, 0), sigmaX=1.0, sigmaY=height * 0.02)
        return self._streaks

    def render(self, frame, background, mask, hidden: float, now: float) -> np.ndarray:
        if hidden <= 0.0:
            return frame
        if hidden >= 1.0:
            return hide_person(frame, background, mask, 1.0)

        # Hoe zichtbaar je bent: flikkeren met steeds meer 'weg', dan volledig weg.
        if hidden < 0.15:
            person = 1.0
        elif hidden < 0.65:
            chance_gone = ramp(hidden, 0.15, 0.65) * 0.85
            gone = random_for_slot(int(now * self.FLICKER_HZ)) < chance_gone
            person = 0.15 if gone else 1.0
        else:
            person = 0.0
        output = hide_person(frame, background, mask, 1.0 - person)

        height, width = mask.shape
        glow = np.zeros_like(mask)
        # Snelheidslijnen: sterkst halverwege, binnen je silhouet, schieten omhoog.
        lines = smoothstep(ramp(hidden, 0.0, 0.25)) * (1.0 - smoothstep(ramp(hidden, 0.7, 1.0)))
        if lines > 0:
            streaks = self._streak_texture(height, width)
            offset = int((now * self.LINE_SPEED % 1.0) * height)
            glow = np.maximum(glow, streaks[offset:offset + height] * (lines * 0.9))
        # Flits: je silhouet licht fel op en verdwijnt.
        flash = ramp(hidden, 0.6, 0.7) * (1.0 - ramp(hidden, 0.72, 0.82))
        if flash > 0:
            glow = np.maximum(glow, np.full_like(mask, flash))
        return add_glow(output, glow * mask)


class GlitchEffect:
    """Digitale storing: je silhouet verspringt in horizontale stroken met kleurverschuiving."""

    name = "glitch"
    GLITCH_HZ = 15.0

    def render(self, frame, background, mask, hidden: float, now: float) -> np.ndarray:
        if hidden <= 0.0:
            return frame
        if hidden >= 1.0:
            return hide_person(frame, background, mask, 1.0)

        height, width = mask.shape
        slot = int(now * self.GLITCH_HZ)
        strength = np.sin(np.pi * hidden)  # sterkst halverwege
        glitched = frame.copy()

        # Stroken die links of rechts verspringen.
        max_shift = int(width * 0.06 * strength) + 1
        row = 0
        band = 0
        while row < height:
            band_height = int(4 + random_for_slot(slot, band) * height * 0.06)
            if random_for_slot(slot, band + 1000) < 0.5 * strength + 0.1:
                shift = int((random_for_slot(slot, band + 2000) * 2 - 1) * max_shift)
                glitched[row:row + band_height] = np.roll(frame[row:row + band_height], shift, axis=1)
            row += band_height
            band += 1

        # Kleurkanalen uit elkaar (blauw naar links, rood naar rechts).
        split = int(width * 0.012 * strength)
        if split > 0:
            blue, green, red = cv2.split(glitched)
            glitched = cv2.merge([np.roll(blue, -split, axis=1), green, np.roll(red, split, axis=1)])

        # Steeds minder van jou zichtbaar, met af en toe een terugval.
        visible = 1.0 - smoothstep(hidden)
        if random_for_slot(slot, 3000) < 0.3 * strength:
            visible = min(1.0, visible + 0.4 * strength)
        person = hide_person(glitched, background, np.ones_like(mask), 1.0 - visible)
        # Alleen binnen het masker: de rest van de kamer blijft het live beeld.
        return hide_person(frame, person, mask, 1.0)


EFFECTS = {effect.name: effect for effect in (TeleportEffect, GlitchEffect, FadeEffect)}


def create_effect(name: str):
    return EFFECTS[name]()


def next_effect_name(name: str) -> str:
    names = list(EFFECTS)
    return names[(names.index(name) + 1) % len(names)]
