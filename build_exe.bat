@echo off
setlocal
cd /d "%~dp0"

rem Python 3.11 is preferred: winsdk has prebuilt wheels only for <= 3.11.
set "PY=py -3.11"
%PY% -c "import sys" >nul 2>&1
if errorlevel 1 set "PY=python"

echo Using: %PY%
%PY% -c "import sys; print('Python', sys.version)"

echo [1/2] Installing build dependencies...
%PY% -m pip install --disable-pip-version-check -r requirements.txt pyinstaller
if errorlevel 1 goto fail

echo [2/2] Building MusicLine.exe ...
%PY% -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name MusicLine ^
  --icon "MusicLine.ico" ^
  --add-data "langs;langs" ^
  --add-data "MusicLineLogo.png;." ^
  --collect-submodules winsdk ^
  --hidden-import lyrics_sources ^
  main.py
if errorlevel 1 goto fail

echo.
echo Build finished: dist\MusicLine.exe
echo Put the exe anywhere; settings.json will be created next to it.
exit /b 0

:fail
echo.
echo Build failed. See the log above.
exit /b 1
