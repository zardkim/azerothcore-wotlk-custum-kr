@echo off
REM Build the player launcher as a single portable exe (dist\WOW Legends.exe).
REM Onefile (not onedir) because this is meant to be downloaded as ONE file from a
REM website link. assets/ and config/ are baked into the exe itself (--add-data) so
REM nothing else needs to ship alongside it. On first run the exe copies itself to
REM C:\wow_launcher and relaunches from there (see ensure_installed() in app.py) -
REM the copy at C:\wow_launcher is what actually stays "installed".
REM
REM NOTE: keep this file ASCII-only (no Korean text) - cmd.exe parses .bat with the
REM system ANSI codepage and UTF-8 Korean bytes can corrupt nearby syntax.
cd /d "%~dp0"

echo [1/2] Checking PyInstaller install...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo     Not installed, installing...
    python -m pip install --quiet pyinstaller
)

echo [2/2] Building (onefile)...
python -m PyInstaller --noconfirm --windowed --onefile ^
    --name "WOW Legends" ^
    --icon "assets\icon.ico" ^
    --add-data "assets;assets" ^
    --add-data "config;config" ^
    app.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo.
echo Done: dist\WOW Legends.exe
echo Edit config\config.json (server address/ports, download_url, realmlist_api_url)
echo BEFORE building - it gets baked into the exe, not read from disk at runtime.
echo Give this single exe to players; running it installs to C:\wow_launcher automatically.
pause
