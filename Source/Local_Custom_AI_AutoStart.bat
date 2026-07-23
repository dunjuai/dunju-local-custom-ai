@echo off
title Dunju AI Backend v1.0.0
echo.
echo ================================================
echo   Dunju AI Backend v1.0.0 - Starting...
echo   Build. Automate. Scale.
echo ================================================
echo.

REM ── Portable: always run from the folder this .bat lives in ──
cd /d "%~dp0"

REM ── Find Python: try PATH first, then the py launcher, then known install ──
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
