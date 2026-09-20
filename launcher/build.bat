@echo off
REM Build WOW Launcher as an exe (creates dist\WOW Launcher\WOW Launcher.exe).
REM Personal config (config.json/presets.json) is NOT bundled - distributed exe always starts clean.
REM
REM Uses onedir instead of onefile - onefile unpacks to a temp folder on every run and
REM deletes it on exit, which can trigger "failed to remove temporary directory" errors
REM (usually from antivirus real-time scanning colliding with cleanup timing). onedir has
REM no such unpack/cleanup step and runs much more reliably.
REM
REM NOTE: this file must stay ASCII-only (no Korean/non-ASCII text). cmd.exe parses .bat
REM files using the system ANSI codepage (CP949 on Korean Windows), and UTF-8 multi-byte
REM Korean text gets misread as garbled double-byte pairs, corrupting nearby syntax like
REM %%v or --version-file. Keep all echo/REM text in English to avoid that entirely.
cd /d "%~dp0"

echo [1/4] Checking PyInstaller install...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo     Not installed, installing...
    python -m pip install --quiet pyinstaller
)

echo [2/4] Bumping version...
for /f "delims=" %%v in ('python bump_version.py') do set NEWVER=%%v
echo     New version: v%NEWVER%

echo [3/4] Building (onedir)...
python -m PyInstaller --noconfirm --windowed --onedir ^
    --name "WOW Launcher" ^
    --icon "assets\icon.ico" ^
    --version-file "version_info.txt" ^
    app.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo [4/4] Copying assets next to the exe (background/logo/font/icon)...
xcopy /E /I /Y "assets" "dist\WOW Launcher\assets" >nul

echo.
echo Done: dist\WOW Launcher\WOW Launcher.exe  (v%NEWVER%)
echo Settings will be created fresh with defaults on first run.
echo   - Move the whole "dist\WOW Launcher" folder anywhere you like (e.g. the WoW client folder).
echo   - The _internal folder next to it is required at runtime - do not delete or move it separately.
pause
