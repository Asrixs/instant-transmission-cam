"""Echte webcam openen en de virtuele camera (OBS Virtual Camera) aansturen."""

from __future__ import annotations

import platform

import cv2
import numpy as np


def open_webcam(index: int, width: int, height: int, fps: float) -> cv2.VideoCapture:
    if platform.system() == "Windows":
        # DirectShow start op Windows veel sneller dan de standaard-backend.
        capture = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if not capture.isOpened():
            capture.release()
            capture = cv2.VideoCapture(index)
    else:
        capture = cv2.VideoCapture(index)

    if not capture.isOpened():
        raise RuntimeError(
            f"Webcam {index} is niet beschikbaar. Sluit andere apps die de camera gebruiken "
            "(Teams, Zoom, browser) of probeer een andere camera met --camera 1."
        )

    # MJPG geeft bij de meeste webcams een hogere framerate op 720p.
    capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    capture.set(cv2.CAP_PROP_FPS, fps)
    capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return capture


class VirtualCamera:
    """Stuurt beelden naar OBS Virtual Camera; doet niets als die niet beschikbaar is."""

    def __init__(self, width: int, height: int, fps: float, required: bool) -> None:
        self.width, self.height = width, height
        self._camera = None
        try:
            import pyvirtualcam

            self._camera = pyvirtualcam.Camera(
                width=width, height=height, fps=fps, fmt=pyvirtualcam.PixelFormat.BGR
            )
        except Exception as error:
            message = (
                "Virtuele camera niet beschikbaar. Controleer of OBS Studio is geïnstalleerd "
                "en of 'Virtuele camera' in OBS zelf UIT staat."
            )
            if required:
                raise RuntimeError(f"{message} ({error})") from error
            print(f"[Camera] {message}")
            print("[Camera] Alleen het voorbeeldvenster wordt getoond.")
            return
        print(f"[Camera] Virtuele camera actief: {self._camera.device} ({width}x{height})")
        print("[Camera] Kies deze camera in Teams, Zoom, Meet of je browser.")

    @property
    def active(self) -> bool:
        return self._camera is not None

    def send(self, frame: np.ndarray) -> None:
        if self._camera is None:
            return
        if frame.shape[1] != self.width or frame.shape[0] != self.height:
            frame = cv2.resize(frame, (self.width, self.height))
        self._camera.send(frame)

    def close(self) -> None:
        if self._camera is not None:
            self._camera.close()
            self._camera = None
