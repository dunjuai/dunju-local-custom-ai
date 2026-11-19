@echo off
title Dunju AI Backend v1.0.1
echo.
echo ================================================
echo   Dunju AI Backend v1.0.1 - Starting...
echo   Build. Automate. Scale.
echo ================================================
echo.
echo   The app will open in your browser at http://127.0.0.1:8000
echo   Keep this window open while you use Dunju AI.
echo.

REM -- Portable: always run from the folder this .bat lives in --
cd /d "%~dp0"

REM -- Open the browser a few seconds after the backend starts --
start "" /b cmd /c "timeout /t 4 /nobreak >nul & start "" http://127.0.0.1:8000"

REM -- Find Python: try PATH first, then the py launcher, then known install --
where python >nul 2>nul
if %errorlevel%==0 (
    python main.py
    goto :end
)
where py >nul 2>nul
if %errorlevel%==0 (
    py main.py
    goto :end
)
if exist "C:\Program Files\Python314\python.exe" (
    "C:\Program Files\Python314\python.exe" main.py
    goto :end
)
echo.
echo   ERROR: Python not found. Please install Python and try again.
echo.

:end
pause
