"""Hoofdprogramma: webcam -> gebaarherkenning -> virtuele camera + voorbeeldvenster."""

from __future__ import annotations

import argparse
import time

import cv2
import numpy as np

from .camera import VirtualCamera, open_webcam
from .detector import Detection, GestureDetector
from .gesture import GestureHold, GestureSettings
from .models import ensure_models

WINDOW_NAME = "Instant Transmission Cam - voorbeeld"
DEBUG_INTERVAL_SECONDS = 0.5
FLASH_SECONDS = 0.6

GREEN = (80, 220, 80)
YELLOW = (40, 200, 255)
WHITE = (255, 255, 255)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verdwijn met het Instant Transmission-gebaar.")
    parser.add_argument("--camera", type=int, default=0, help="nummer van je webcam (standaard 0)")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    parser.add_argument("--fps", type=float, default=30.0)
    parser.add_argument("--hold", type=float, default=1.0, help="seconden dat je het gebaar moet vasthouden")
    parser.add_argument(
        "--virtual-camera", action=argparse.BooleanOptionalAction, default=None,
        help="--virtual-camera: stop als de virtuele camera niet werkt; "
             "--no-virtual-camera: alleen het voorbeeldvenster",
    )
    parser.add_argument("--debug", action="store_true", help="toon meetwaarden van het gebaar in de terminal")
    return parser.parse_args()


def draw_overlay(preview: np.ndarray, detection: Detection, progress: float) -> None:
    """Hulplijnen in het voorbeeldvenster. Deze komen nooit in de virtuele camera."""
    for hand_px in detection.hands_px:
        for point in hand_px:
            cv2.circle(preview, tuple(int(v) for v in point), 2, WHITE, -1, cv2.LINE_AA)
    if detection.face is None:
        return
    center = tuple(int(v) for v in detection.face.forehead_px)
    radius = max(12, int(detection.face.eye_distance_px * 0.35))
    cv2.circle(preview, center, radius, WHITE, 1, cv2.LINE_AA)
    if progress > 0:
        cv2.ellipse(preview, center, (radius, radius), -90, 0, 360 * progress, GREEN, 4, cv2.LINE_AA)
    if detection.best is not None:
        tips = tuple(int(v) for v in detection.best.fingertips_px)
        cv2.circle(preview, tips, 7, GREEN if detection.active else YELLOW, -1, cv2.LINE_AA)


def draw_status(preview: np.ndarray, lines: list[str]) -> None:
    for row, text in enumerate(lines):
        position = (12, 28 + row * 26)
        cv2.putText(preview, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(preview, text, position, cv2.FONT_HERSHEY_SIMPLEX, 0.65, WHITE, 1, cv2.LINE_AA)


def main() -> int:
    args = parse_args()
    settings = GestureSettings(hold_seconds=args.hold)

    ensure_models()
    capture = open_webcam(args.camera, args.width, args.height, args.fps)
    ok, frame = capture.read()
    if not ok:
        capture.release()
        raise RuntimeError("De webcam geeft geen beeld. Is hij in gebruik door een andere app?")
    height, width = frame.shape[:2]
    print(f"[Camera] Webcam {args.camera} geopend ({width}x{height})")

    virtual = (
        VirtualCamera(width, height, args.fps, required=bool(args.virtual_camera))
        if args.virtual_camera is not False
        else None
    )
    detector = GestureDetector(settings)
    hold = GestureHold(settings.hold_seconds, settings.grace_seconds)

    print("[Klaar] Leg wijs- en middelvinger tegen je voorhoofd en houd dat "
          f"{settings.hold_seconds:g} seconde vast.")
    print("[Klaar] Toetsen in het voorbeeldvenster: Q/Esc = stoppen, H = hulplijnen aan/uit, M = spiegelen.")

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    show_overlay, mirror = True, True
    trigger_count = 0
    flash_until = 0.0
    last_debug = 0.0
    failed_reads = 0

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                failed_reads += 1
                if failed_reads > 30:
                    raise RuntimeError("De webcam stopt met beeld geven.")
                continue
            failed_reads = 0
            now = time.monotonic()

            detection = detector.detect(frame)
            update = hold.update(detection.active, now)
            if update.triggered:
                trigger_count += 1
                flash_until = now + FLASH_SECONDS
                print(f"[Gebaar] Instant Transmission herkend! ({trigger_count}x)")

            if args.debug and detection.best is not None and now - last_debug >= DEBUG_INTERVAL_SECONDS:
                last_debug = now
                state = "JA " if detection.active else "nee"
                print(f"[Debug] gebaar={state} {detection.best.describe()}")

            # De virtuele camera krijgt het schone beeld, zonder hulplijnen of tekst.
            if virtual is not None:
                virtual.send(frame)

            preview = frame.copy()
            if show_overlay:
                draw_overlay(preview, detection, update.progress)
            if mirror:
                preview = cv2.flip(preview, 1)
            if now < flash_until:
                cv2.rectangle(preview, (0, 0), (width - 1, height - 1), GREEN, 12)
            if show_overlay:
                virtual_state = "aan" if virtual is not None and virtual.active else "uit"
                draw_status(preview, [
                    f"Virtuele camera: {virtual_state}",
                    f"Gebaar: {int(update.progress * 100)}%   herkend: {trigger_count}x",
                ])
            cv2.imshow(WINDOW_NAME, preview)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            if key in (ord("h"), ord("H")):
                show_overlay = not show_overlay
            if key in (ord("m"), ord("M")):
                mirror = not mirror
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        detector.close()
        if virtual is not None:
            virtual.close()
        capture.release()
        cv2.destroyAllWindows()
    return 0
