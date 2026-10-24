"""Koppeling met MediaPipe: bepaalt per beeld welke pixels bij jou horen."""

from __future__ import annotations

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from .detector import MonotonicTimestamps
from .models import SEGMENTER_MODEL

# Het model werkt intern op 256x144; groter aanleveren heeft geen zin.
SEGMENT_WIDTH = 320


class PersonSegmenter:
    def __init__(self) -> None:
        self._segmenter = vision.ImageSegmenter.create_from_options(
            vision.ImageSegmenterOptions(
                base_options=BaseOptions(model_asset_path=str(SEGMENTER_MODEL)),
                running_mode=vision.RunningMode.VIDEO,
                output_confidence_masks=True,
                output_category_mask=False,
            )
        )
        self._timestamps = MonotonicTimestamps()

    def close(self) -> None:
        self._segmenter.close()

    def segment(self, frame_bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """Geeft (zekerheid per pixel 0..1, verkleind beeld) terug, beide op lage resolutie."""
        height, width = frame_bgr.shape[:2]
        small = cv2.resize(frame_bgr, (SEGMENT_WIDTH, round(height * SEGMENT_WIDTH / width)))
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(small, cv2.COLOR_BGR2RGB))
        result = self._segmenter.segment_for_video(image, self._timestamps.next())
        if not result.confidence_masks:
            return np.zeros(small.shape[:2], dtype=np.float32), small
        confidence = np.squeeze(result.confidence_masks[0].numpy_view()).astype(np.float32)
        if confidence.shape != small.shape[:2]:
            confidence = cv2.resize(confidence, (small.shape[1], small.shape[0]))
        return confidence, small
