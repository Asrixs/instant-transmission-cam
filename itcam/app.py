"""Hoofdprogramma: webcam -> gebaarherkenning -> verdwijnen -> virtuele camera + voorbeeldvenster."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import numpy as np

from .camera import VirtualCamera, open_webcam
from .detector import Detection, GestureDetector
from .effects import EFFECTS, create_effect, next_effect_name
from .gesture import GestureHold, GestureSettings
from .models import ensure_models
from .segmenter import PersonSegmenter
from .sound import SoundPlayer
from .vanish import (
    BackgroundCapture,
    BrightnessMatcher,
    CaptureStatus,
    Visibility,
    difference_mask,
    person_fraction,
    prepare_mask,
)

WINDOW_NAME = "Instant Transmission Cam - voorbeeld"
DEBUG_INTERVAL_SECONDS = 0.5
FLASH_SECONDS = 0.6
INSET_SCALE = 0.25

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
    parser.add_argument("--countdown", type=float, default=4.0,
                        help="seconden om uit beeld te stappen voordat de achtergrond wordt vastgelegd")
    parser.add_argument("--transition", type=float, default=0.8, help="duur van verdwijnen/verschijnen in seconden")
    parser.add_argument("--effect", choices=list(EFFECTS), default="teleport",
                        help="effect bij verdwijnen/verschijnen (wisselen met E in het voorbeeldvenster)")
    parser.add_argument("--volume", type=float, default=0.8, help="volume van het teleportgeluid, 0 = uit (standaard 0.8)")
    parser.add_argument("--no-sound", action="store_true", help="geen teleportgeluid")
    parser.add_argument("--sound", type=Path, help="eigen geluid (16-bit WAV-bestand) in plaats van het teleportgeluid")
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


def draw_text(preview: np.ndarray, text: str, position: tuple[int, int], scale: float, thickness: int) -> None:
    cv2.putText(preview, text, position, cv2.FONT_HERSHEY_SIMPLEX, scale, (0, 0, 0), thickness + 3, cv2.LINE_AA)
    cv2.putText(preview, text, position, cv2.FONT_HERSHEY_SIMPLEX, scale, WHITE, thickness, cv2.LINE_AA)


def draw_status(preview: np.ndarray, lines: list[str]) -> None:
    for row, text in enumerate(lines):
        draw_text(preview, text, (12, 28 + row * 26), 0.65, 1)


def draw_banner(preview: np.ndarray, text: str) -> None:
    """Grote tekst midden in beeld, bijvoorbeeld het aftellen."""
    (text_width, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.4, 3)
    height, width = preview.shape[:2]
    draw_text(preview, text, ((width - text_width) // 2, height // 2), 1.4, 3)


def draw_inset(preview: np.ndarray, camera: np.ndarray) -> None:
    """Klein live camerabeeld in de hoek, zodat je jezelf ziet terwijl je onzichtbaar bent."""
    height, width = preview.shape[:2]
    small = cv2.resize(camera, (int(width * INSET_SCALE), int(height * INSET_SCALE)))
    top, left = 12, width - small.shape[1] - 12
    preview[top:top + small.shape[0], left:left + small.shape[1]] = small
    cv2.rectangle(preview, (left, top), (left + small.shape[1], top + small.shape[0]), WHITE, 1)
    draw_text(preview, "jij (alleen hier)", (left + 6, top + small.shape[0] - 8), 0.5, 1)


def capture_banner(status: CaptureStatus) -> str:
    if status.phase == "countdown":
        return f"Stap uit beeld: {int(status.seconds_left) + 1}"
    if status.phase == "waiting":
        return "Je bent nog in beeld - stap opzij"
    return "Lege kamer vastleggen..."


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
    segmenter = PersonSegmenter()
    hold = GestureHold(settings.hold_seconds, settings.grace_seconds)
    background_capture = BackgroundCapture(args.countdown)
    visibility = Visibility(args.transition)
    effect = create_effect(args.effect)
    sound = SoundPlayer(args.transition, 0.0 if args.no_sound else args.volume, args.sound)
    brightness = BrightnessMatcher()
    background: np.ndarray | None = None
    background_small: np.ndarray | None = None

    print("[Klaar] Toetsen in het voorbeeldvenster: Spatie = lege kamer opnieuw vastleggen, "
          "V = verdwijnen/verschijnen zonder gebaar, E = ander effect, S = geluid aan/uit, "
          "H = hulplijnen, M = spiegelen, "
          "Q/Esc = stoppen.")
    print(f"[Effect] {effect.name}")
    print(f"[Achtergrond] Stap uit beeld: over {args.countdown:g} seconden wordt de lege kamer vastgelegd.")
    background_capture.start(time.monotonic())

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)
    show_overlay, mirror = True, True
    trigger_count = 0
    flash_until = 0.0
    last_debug = 0.0
    last_capture_phase = None
    failed_reads = 0

    def toggle_visibility() -> None:
        if background is None:
            print("[Gebaar] Er is nog geen lege kamer vastgelegd. Druk op spatie en stap uit beeld.")
            return
        visibility.toggle()
        if visibility.visible:
            sound.play_appear()
            print("[Gebaar] Je bent weer zichtbaar.")
        else:
            sound.play_vanish()
            print("[Gebaar] Instant Transmission! Je bent nu onzichtbaar.")

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
                toggle_visibility()

            problems = detection.best.problems(settings) if detection.best is not None else []
            if args.debug and detection.best is not None and now - last_debug >= DEBUG_INTERVAL_SECONDS:
                last_debug = now
                state = "JA " if detection.active else "nee"
                reason = f"  ({', '.join(problems)})" if problems else ""
                print(f"[Debug] gebaar={state} {detection.best.describe()}{reason}")

            hidden = visibility.update(now)
            output = frame
            checking_background = background_capture.needs_check(now)
            if checking_background or (hidden > 0 and background is not None):
                confidence, small = segmenter.segment(frame)
                if checking_background:
                    captured = background_capture.update(frame, person_fraction(confidence), now)
                    if captured is not None:
                        background = captured
                        background_small = cv2.resize(background, (small.shape[1], small.shape[0]))
                        brightness.reset()
                        print("[Achtergrond] Lege kamer vastgelegd! Kom maar terug in beeld.")
                if hidden > 0 and background is not None and background_small is not None:
                    brightness.update(small, background_small, confidence)
                    difference = difference_mask(small, brightness.apply(background_small))
                    mask = prepare_mask(confidence, (width, height), difference)
                    output = effect.render(frame, brightness.apply(background), mask, hidden, now)

            capture_status = background_capture.status(now)
            if capture_status is not None and capture_status.phase != last_capture_phase:
                if capture_status.phase == "waiting":
                    print("[Achtergrond] Je bent nog in beeld. Stap helemaal opzij.")
            last_capture_phase = capture_status.phase if capture_status is not None else None

            # De virtuele camera krijgt het schone beeld, zonder hulplijnen of tekst.
            if virtual is not None:
                virtual.send(output)

            preview = output.copy()
            if show_overlay:
                draw_overlay(preview, detection, update.progress)
            if mirror:
                preview = cv2.flip(preview, 1)
            if now < flash_until:
                cv2.rectangle(preview, (0, 0), (width - 1, height - 1), GREEN, 12)
            if show_overlay:
                if hidden > 0:
                    draw_inset(preview, cv2.flip(frame, 1) if mirror else frame)
                virtual_state = "aan" if virtual is not None and virtual.active else "uit"
                if background is None:
                    state = "nog geen lege kamer (spatie)"
                else:
                    state = "zichtbaar" if visibility.visible else "onzichtbaar"
                status = [
                    f"Virtuele camera: {virtual_state}",
                    f"Status: {state}   effect: {effect.name} (E)   geluid: {'aan' if sound.enabled else 'uit'} (S)",
                    f"Gebaar: {int(update.progress * 100)}%   herkend: {trigger_count}x",
                ]
                if problems:
                    status.append(f"Mist nog: {', '.join(problems)}")
                draw_status(preview, status)
            if capture_status is not None:
                draw_banner(preview, capture_banner(capture_status))
            cv2.imshow(WINDOW_NAME, preview)

            key = cv2.waitKey(1) & 0xFF
            if key in (ord("q"), ord("Q"), 27):
                break
            if key == ord(" "):
                visibility.show_now()
                background_capture.start(now)
                print(f"[Achtergrond] Stap uit beeld: over {args.countdown:g} seconden wordt "
                      "de lege kamer opnieuw vastgelegd.")
            if key in (ord("v"), ord("V")):
                toggle_visibility()
            if key in (ord("e"), ord("E")):
                effect = create_effect(next_effect_name(effect.name))
                print(f"[Effect] {effect.name}")
            if key in (ord("s"), ord("S")):
                print(f"[Geluid] {'aan' if sound.toggle() else 'uit'}")
            if key in (ord("h"), ord("H")):
                show_overlay = not show_overlay
            if key in (ord("m"), ord("M")):
                mirror = not mirror
            if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        detector.close()
        segmenter.close()
        if virtual is not None:
            virtual.close()
        capture.release()
        cv2.destroyAllWindows()
    return 0
