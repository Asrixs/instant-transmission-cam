"""Herkenning van het Instant Transmission-gebaar: wijs- en middelvinger
gestrekt en tegen elkaar, ring- en pink ingevouwen, vingertoppen op het voorhoofd.

Dit bestand bevat alleen rekenwerk op landmarks (numpy-arrays), zodat het
zonder camera of MediaPipe getest kan worden.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# MediaPipe-handpunten (zie de "hand landmarks"-afbeelding in de MediaPipe-docs).
WRIST = 0
INDEX_MCP, INDEX_PIP, INDEX_TIP = 5, 6, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP = 9, 10, 12
RING_PIP, RING_TIP = 14, 16
PINKY_PIP, PINKY_TIP = 18, 20


@dataclass(frozen=True)
class GestureSettings:
    # Vinger telt als gestrekt als de top zoveel verder van de pols ligt dan het middelste kootje.
    extended_ratio: float = 1.2
    # Vinger telt als ingevouwen als de top hooguit zoveel verder van de pols ligt dan het middelste kootje.
    folded_ratio: float = 1.1
    # Maximale afstand tussen de twee vingertoppen, relatief aan de handgrootte.
    max_tip_gap: float = 0.45
    # Maximale afstand tussen vingertoppen en voorhoofd, relatief aan de oogafstand.
    max_forehead_distance: float = 0.9
    # Zo lang moet het gebaar worden vastgehouden.
    hold_seconds: float = 1.0
    # Zo lang mag de herkenning even wegvallen zonder dat de teller opnieuw begint.
    grace_seconds: float = 0.25


@dataclass(frozen=True)
class GestureMeasurement:
    index_ratio: float
    middle_ratio: float
    ring_ratio: float
    pinky_ratio: float
    tip_gap: float
    forehead_distance: float
    fingertips_px: np.ndarray  # middelpunt van wijs- en middelvingertop, in pixels

    def matches(self, settings: GestureSettings) -> bool:
        return (
            self.index_ratio >= settings.extended_ratio
            and self.middle_ratio >= settings.extended_ratio
            and self.ring_ratio <= settings.folded_ratio
            and self.pinky_ratio <= settings.folded_ratio
            and self.tip_gap <= settings.max_tip_gap
            and self.forehead_distance <= settings.max_forehead_distance
        )

    def describe(self) -> str:
        return (
            f"wijs={self.index_ratio:.2f} midden={self.middle_ratio:.2f} "
            f"ring={self.ring_ratio:.2f} pink={self.pinky_ratio:.2f} "
            f"tussenruimte={self.tip_gap:.2f} voorhoofd={self.forehead_distance:.2f}"
        )


def _distance(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.linalg.norm(a - b))


def _finger_ratio(world: np.ndarray, pip: int, tip: int) -> float:
    wrist = world[WRIST]
    return _distance(world[tip], wrist) / max(_distance(world[pip], wrist), 1e-6)


def measure_hand(
    hand_world: np.ndarray,
    hand_px: np.ndarray,
    forehead_px: np.ndarray,
    eye_distance_px: float,
) -> GestureMeasurement:
    """Meet één hand ten opzichte van het voorhoofd.

    hand_world: 21x3 MediaPipe-wereldcoördinaten (meters); daarmee maakt de stand
    van de hand t.o.v. de camera weinig uit.
    hand_px: 21x2 beeldcoördinaten in pixels.
    forehead_px: punt midden op het voorhoofd in pixels.
    eye_distance_px: afstand tussen de buitenste ooghoeken in pixels (gezichtsschaal).
    """
    hand_size = max(_distance(hand_world[WRIST], hand_world[MIDDLE_MCP]), 1e-6)
    fingertips_px = (hand_px[INDEX_TIP] + hand_px[MIDDLE_TIP]) / 2.0
    return GestureMeasurement(
        index_ratio=_finger_ratio(hand_world, INDEX_PIP, INDEX_TIP),
        middle_ratio=_finger_ratio(hand_world, MIDDLE_PIP, MIDDLE_TIP),
        ring_ratio=_finger_ratio(hand_world, RING_PIP, RING_TIP),
        pinky_ratio=_finger_ratio(hand_world, PINKY_PIP, PINKY_TIP),
        tip_gap=_distance(hand_world[INDEX_TIP], hand_world[MIDDLE_TIP]) / hand_size,
        forehead_distance=_distance(fingertips_px, forehead_px) / max(eye_distance_px, 1e-6),
        fingertips_px=fingertips_px,
    )


@dataclass(frozen=True)
class HoldUpdate:
    progress: float  # 0..1, hoe lang het gebaar al wordt vastgehouden
    triggered: bool  # True op precies het moment dat de houdtijd vol is


class GestureHold:
    """Telt hoe lang het gebaar wordt vastgehouden.

    Na een trigger moet de hand eerst weg (langer dan grace_seconds) voordat
    het gebaar opnieuw kan triggeren, zodat één keer vasthouden één actie is.
    """

    def __init__(self, hold_seconds: float, grace_seconds: float) -> None:
        self.hold_seconds = hold_seconds
        self.grace_seconds = grace_seconds
        self._start: float | None = None
        self._last_active = 0.0
        self._fired = False

    def update(self, active: bool, now: float) -> HoldUpdate:
        if active:
            if self._start is None:
                self._start = now
            self._last_active = now
        elif self._start is not None and now - self._last_active > self.grace_seconds:
            self._start = None
            self._fired = False

        if self._start is None:
            return HoldUpdate(0.0, False)
        progress = min((self._last_active - self._start) / self.hold_seconds, 1.0)
        if progress >= 1.0 and not self._fired:
            self._fired = True
            return HoldUpdate(1.0, True)
        return HoldUpdate(progress, False)
