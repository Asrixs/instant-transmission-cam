@echo off
setlocal
cd /d "%~dp0"

set "VENV_PY=.venv\Scripts\python.exe"
rem pyvirtualcam heeft alleen versies voor Python 3.11 t/m 3.14.
set "CHECK_VERSION=import sys; sys.exit(0 if (3, 11) <= sys.version_info[:2] <= (3, 14) else 1)"

rem Een omgeving met een niet-ondersteunde Python-versie wordt opnieuw gemaakt.
if exist "%VENV_PY%" (
  "%VENV_PY%" -c "%CHECK_VERSION%" >nul 2>nul
  if errorlevel 1 (
    echo [Start] De Python-omgeving gebruikt een niet-ondersteunde Python-versie, opnieuw aanmaken...
    rmdir /s /q .venv
  )
)

if exist "%VENV_PY%" goto :have_venv
call :find_python
if not defined PYTHON_CMD goto :no_python
echo [Start] Python-omgeving aanmaken met %PYTHON_CMD%, eenmalig...
%PYTHON_CMD% -m venv .venv
if errorlevel 1 goto :error
:have_venv

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

:find_python
rem Zoek een geïnstalleerde Python 3.11 t/m 3.14, bij voorkeur 3.13.
set "PYTHON_CMD="
for %%V in (3.13 3.12 3.14 3.11) do (
  if not defined PYTHON_CMD (
    py -%%V -c "%CHECK_VERSION%" >nul 2>nul && set "PYTHON_CMD=py -%%V"
  )
)
if not defined PYTHON_CMD (
  python -c "%CHECK_VERSION%" >nul 2>nul && set "PYTHON_CMD=python"
)
exit /b 0

:no_python
echo.
echo [Start] Geen geschikte Python-versie gevonden. Dit project werkt met Python 3.11 t/m 3.14.
echo [Start] Installeer Python 3.13 naast je huidige versie, bijvoorbeeld met:  py install 3.13
echo [Start] Start daarna start.bat opnieuw. Zie de README voor meer uitleg.
pause
exit /b 1

:error
echo.
echo Er ging iets mis. Lees de melding hierboven en de README.
pause
exit /b 1
