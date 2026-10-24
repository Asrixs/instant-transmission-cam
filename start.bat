@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"

if not exist "%VENV_PY%" (
  echo [Start] Python-omgeving aanmaken, eenmalig...
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 -m venv .venv
  ) else (
    python -m venv .venv
  )
  if errorlevel 1 goto :error
)

rem Installeer opnieuw als requirements.txt is veranderd sinds de vorige keer.
fc /b requirements.txt .venv\requirements.installed >nul 2>nul
if errorlevel 1 (
  echo [Start] Onderdelen installeren, internet nodig...
  "%VENV_PY%" -m pip install --upgrade pip
  if errorlevel 1 goto :error
  "%VENV_PY%" -m pip install -r requirements.txt
  if errorlevel 1 goto :error
  copy /y requirements.txt .venv\requirements.installed >nul
)

"%VENV_PY%" -m itcam %*
if errorlevel 1 goto :error
exit /b 0

:error
echo.
echo Er ging iets mis. Lees de melding hierboven en de README.
pause
exit /b 1
