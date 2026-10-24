# PyInstaller-recept voor InstantTransmissionCam.exe. Bouwen: build_exe.bat
# (of: python -m PyInstaller --noconfirm InstantTransmissionCam.spec)

import shutil
from pathlib import Path

from PyInstaller.utils.hooks import collect_all

NAME = "InstantTransmissionCam"
ROOT = Path(SPECPATH)

# MediaPipe laadt zijn C-bibliotheek en modelbestanden zelf in; neem alles mee.
datas, binaries, hiddenimports = collect_all("mediapipe")
# De herkenningsmodellen zitten ingebouwd, zodat de .exe zonder internet werkt.
datas += [(str(path), "models") for path in sorted((ROOT / "models").glob("*")) if path.suffix in (".task", ".tflite")]
if len([d for d in datas if d[1] == "models"]) != 3:
    raise SystemExit("Modellen ontbreken in models/. Draai eerst: python -m itcam --self-test")

analysis = Analysis(
    [str(ROOT / "itcam_launcher.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest"],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
exe = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    icon=str(ROOT / "assets" / "icon.ico"),
    console=True,  # het terminalvenster toont de meldingen (stap uit beeld, gebaar herkend, ...)
    upx=False,
)
COLLECT(exe, analysis.binaries, analysis.datas, name=NAME, upx=False)

# Map voor een eigen geluid naast de .exe, met uitleg.
sounds = Path(DISTPATH) / NAME / "sounds"
sounds.mkdir(exist_ok=True)
shutil.copy(ROOT / "sounds" / "README.md", sounds / "README.md")
