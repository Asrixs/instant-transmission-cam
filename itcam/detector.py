"""Koppeling met MediaPipe: vindt voorhoofd en handen in een camerabeeld."""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from .gesture import GestureMeasurement, GestureSettings, measure_hand
from .models import FACE_MODEL, HAND_MODEL

# Face Mesh-punten: midden voorhoofd en de buitenste ooghoeken.
FOREHEAD = 151
LEFT_EYE_OUTER, RIGHT_EYE_OUTER = 33, 263

# Beelden worden voor de herkenning verkleind; dat is sneller en even nauwkeurig.
DETECTION_WIDTH = 640
# Als je hand het gezicht even afdekt, onthouden we het voorhoofd nog zo lang.
FACE_MEMORY_SECONDS = 1.0


@dataclass(frozen=True)
class Face:
    forehead_px: np.ndarray
    eye_distance_px: float


@dataclass(frozen=True)
class Detection:
    face: Face | None
    hands_px: list[np.ndarray]
    best: GestureMeasurement | None  # hand die het dichtst bij het gebaar zit
    active: bool  # gebaar wordt nu gemaakt


class GestureDetector:
    def __init__(self, settings: GestureSettings) -> None:
        self.settings = settings
        self._faces = vision.FaceLandmarker.create_from_options(
            vision.FaceLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(FACE_MODEL)),
                running_mode=vision.RunningMode.VIDEO,
                num_faces=1,
            )
        )
        self._hands = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=str(HAND_MODEL)),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
                min_hand_detection_confidence=0.4,
                min_hand_presence_confidence=0.4,
                min_tracking_confidence=0.5,
            )
        )
        self._last_timestamp = -1
        self._last_face: Face | None = None
        self._last_face_time = 0.0

    def close(self) -> None:
        self._faces.close()
        self._hands.close()

    def _timestamp_ms(self) -> int:
        # MediaPipe eist strikt oplopende tijdstempels.
        timestamp = max(int(time.monotonic() * 1000), self._last_timestamp + 1)
        self._last_timestamp = timestamp
        return timestamp

    def detect(self, frame_bgr: np.ndarray) -> Detection:
        height, width = frame_bgr.shape[:2]
        scale = min(1.0, DETECTION_WIDTH / width)
        small = cv2.resize(frame_bgr, None, fx=scale, fy=scale) if scale < 1.0 else frame_bgr
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        timestamp = self._timestamp_ms()
        size = np.array([width, height], dtype=np.float32)

        face = self._find_face(self._faces.detect_for_video(image, timestamp), size)
        hand_result = self._hands.detect_for_video(image, timestamp)

        hands_px: list[np.ndarray] = []
        best: GestureMeasurement | None = None
        for landmarks, world in zip(hand_result.hand_landmarks, hand_result.hand_world_landmarks):
            hand_px = np.array([[p.x, p.y] for p in landmarks], dtype=np.float32) * size
            hands_px.append(hand_px)
            if face is None:
                continue
            hand_world = np.array([[p.x, p.y, p.z] for p in world], dtype=np.float32)
            measurement = measure_hand(hand_world, hand_px, face.forehead_px, face.eye_distance_px)
            if best is None or measurement.forehead_distance < best.forehead_distance:
                best = measurement

        active = best is not None and best.matches(self.settings)
        return Detection(face=face, hands_px=hands_px, best=best, active=active)

    def _find_face(self, result: vision.FaceLandmarkerResult, size: np.ndarray) -> Face | None:
        now = time.monotonic()
        if result.face_landmarks:
            points = result.face_landmarks[0]

            def px(index: int) -> np.ndarray:
                return np.array([points[index].x, points[index].y], dtype=np.float32) * size

            self._last_face = Face(
                forehead_px=px(FOREHEAD),
                eye_distance_px=float(np.linalg.norm(px(LEFT_EYE_OUTER) - px(RIGHT_EYE_OUTER))),
            )
            self._last_face_time = now
        elif now - self._last_face_time > FACE_MEMORY_SECONDS:
            self._last_face = None
        return self._last_face
