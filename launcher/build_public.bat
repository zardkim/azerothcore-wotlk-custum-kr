@echo off
REM Build a PUBLIC/redistributable build of WOW Launcher for other users.
REM Differences from build.bat:
REM  - Does NOT bump the version (keeps whatever version.py currently has,
REM    so public releases don't consume version numbers from personal builds).
REM  - Excludes assets\fonts\ (the Cinzel font) from the copied assets - the
REM    app already falls back to a system font automatically if it's missing.
REM  - Never bundles config.json/presets.json (same as build.bat already does) -
REM    a fresh install always starts with default settings.
REM  - Builds into dist_public\ instead of dist\ so it never overwrites your
REM    personal build.
REM
REM NOTE: keep this file ASCII-only, same reason as build.bat (cmd.exe parses
REM .bat files using the system ANSI codepage, and UTF-8 Korean text corrupts
REM nearby syntax like %%v or --version-file - see build.bat for the full story).
cd /d "%~dp0"

echo [1/4] Checking PyInstaller install...
python -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo     Not installed, installing...
    python -m pip install --quiet pyinstaller
)

echo [2/4] Reading current version (public builds do not bump it)...
for /f "delims=" %%v in ('python -c "from version import __version__; print(__version__)"') do set CURVER=%%v
echo     Version: v%CURVER%

echo [3/4] Building (onedir)...
python -m PyInstaller --noconfirm --windowed --onedir ^
    --name "WOW Launcher" ^
    --icon "assets\icon.ico" ^
    --version-file "version_info.txt" ^
    --distpath "dist_public" ^
    app.py
if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo [4/4] Copying assets next to the exe, then removing the font...
xcopy /E /I /Y "assets" "dist_public\WOW Launcher\assets" >nul
if exist "dist_public\WOW Launcher\assets\fonts" rmdir /s /q "dist_public\WOW Launcher\assets\fonts"

echo.
echo Done: dist_public\WOW Launcher\WOW Launcher.exe  (v%CURVER%)
echo This build has no personal settings baked in and no bundled font file -
echo safe to share with other people.
echo   - Move the whole "dist_public\WOW Launcher" folder to distribute it.
echo   - The _internal folder next to it is required at runtime - do not delete or move it separately.
pause
