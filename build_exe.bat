@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
set "NAME=InstantTransmissionCam"

rem Python-omgeving, onderdelen en modellen klaarzetten via start.bat (zonder camera).
call start.bat --self-test
if errorlevel 1 goto :error

echo [Bouwen] PyInstaller installeren...
"%VENV_PY%" -m pip install --quiet pyinstaller==6.22.3
if errorlevel 1 goto :error

echo [Bouwen] %NAME%.exe maken, dit duurt een paar minuten...
"%VENV_PY%" -m PyInstaller --noconfirm --log-level WARN %NAME%.spec
if errorlevel 1 goto :error

echo [Bouwen] Zelftest van de .exe...
"dist\%NAME%\%NAME%.exe" --self-test
if errorlevel 1 goto :error

echo [Bouwen] Zip maken...
powershell -NoProfile -Command "Compress-Archive -Path 'dist\%NAME%' -DestinationPath 'dist\%NAME%.zip' -Force"
if errorlevel 1 goto :error

echo.
echo Klaar! Het programma staat in: dist\%NAME%\%NAME%.exe
echo Om te delen of te bewaren:      dist\%NAME%.zip
pause
exit /b 0

:error
echo.
echo Bouwen mislukt. Lees de melding hierboven.
pause
exit /b 1
