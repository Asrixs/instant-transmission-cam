"""Download van de MediaPipe-modellen (eenmalig, daarna lokaal)."""

from __future__ import annotations

import urllib.request
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parent.parent / "models"
FACE_MODEL = MODEL_DIR / "face_landmarker.task"
HAND_MODEL = MODEL_DIR / "hand_landmarker.task"

MODEL_URLS = {
    FACE_MODEL: (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/latest/face_landmarker.task"
    ),
    HAND_MODEL: (
        "https://storage.googleapis.com/mediapipe-models/hand_landmarker/"
        "hand_landmarker/float16/latest/hand_landmarker.task"
    ),
}


def ensure_models() -> None:
    MODEL_DIR.mkdir(exist_ok=True)
    for path, url in MODEL_URLS.items():
        if path.is_file() and path.stat().st_size > 0:
            continue
        print(f"[Modellen] {path.name} downloaden...")
        partial = path.with_suffix(".part")
        urllib.request.urlretrieve(url, partial)
        partial.replace(path)
