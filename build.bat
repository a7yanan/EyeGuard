@echo off
chcp 65001 >nul
setlocal EnableExtensions
cd /d "%~dp0"
set "PY=python"

echo [1/5] Checking Python...
%PY% --version >nul 2>&1
if errorlevel 1 (
    echo [!] Python was not found. Install Python 3 and tick "Add python.exe to PATH".
    goto fail
)

echo [2/5] Checking libraries (installed only if missing)...
%PY% -m pip show Pillow >nul 2>&1
if errorlevel 1 (
    echo     Installing Pillow...
    %PY% -m pip install Pillow || goto fail
)
%PY% -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo     Installing PyInstaller...
    %PY% -m pip install pyinstaller || goto fail
)

echo [3/5] Creating icons and building EyeGuard.exe...
%PY% make_icon.py || goto fail
%PY% -m PyInstaller --noconsole --onefile --clean --name EyeGuard --icon app.ico --hidden-import cities --add-data "app.ico;." --add-data "logo.png;." --add-data "tray_on.ico;." --add-data "tray_off.ico;." eyeguard.py || goto fail

echo [4/5] Building the setup window (with the program inside)...
%PY% -m PyInstaller --noconsole --onefile --uac-admin --name EyeGuard_Setup --icon app.ico --hidden-import PIL._tkinter_finder --add-data "logo.png;." --add-data "app.ico;." --add-data "dist\EyeGuard.exe;." setup_ui.py
if errorlevel 1 (
    echo [!] The setup window could not be built. Send the messages above to the developer.
    goto fail
)

echo [5/5] Cleaning up...
rmdir /s /q build 2>nul
del /q EyeGuard.spec EyeGuard_Setup.spec 2>nul
if not exist "dist\EyeGuard_Setup.exe" (
    echo [!] The installer file was not created.
    goto fail
)

echo.
echo ==============================================
echo تم! المثبت جاهز: dist\EyeGuard_Setup.exe
echo ==============================================
echo.
pause
exit /b 0

:fail
echo.
echo [!] Build stopped. Read the message above, fix it, then run build.bat again.
pause
exit /b 1
