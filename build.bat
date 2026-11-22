@echo off
setlocal EnableExtensions
cd /d "%~dp0"

set "PYTHON="
where py >nul 2>&1
if not errorlevel 1 (
    py -3 --version >nul 2>&1
    if not errorlevel 1 set "PYTHON=py -3"
)
if not defined PYTHON (
    where python >nul 2>&1
    if not errorlevel 1 (
        python --version >nul 2>&1
        if not errorlevel 1 set "PYTHON=python"
    )
)

if not defined PYTHON goto no_python

echo [1/5] Checking Python...
%PYTHON% --version
if errorlevel 1 goto failed

echo [2/5] Checking required packages...
%PYTHON% -m pip --version >nul 2>&1
if errorlevel 1 (
    echo Installing pip...
    %PYTHON% -m ensurepip --upgrade
    if errorlevel 1 goto failed
)
%PYTHON% -m pip show Pillow >nul 2>&1
if errorlevel 1 (
    echo Installing Pillow...
    %PYTHON% -m pip install Pillow
    if errorlevel 1 goto failed
)
%PYTHON% -m pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    %PYTHON% -m pip install PyInstaller
    if errorlevel 1 goto failed
)

echo [3/5] Creating icons and building EyeGuard...
%PYTHON% make_icon.py
if errorlevel 1 goto failed
%PYTHON% -m PyInstaller --noconsole --onefile --clean --name EyeGuard --icon app.ico --hidden-import cities --add-data "app.ico;." --add-data "logo.png;." --add-data "tray_on.ico;." --add-data "tray_off.ico;." eyeguard.py
if errorlevel 1 goto failed
copy /y "dist\EyeGuard.exe" "dist\EyeGuard.portable.exe" >nul
if errorlevel 1 goto failed

echo [4/5] Building the installer...
%PYTHON% -m PyInstaller --noconsole --onefile --uac-admin --name EyeGuard_Setup --icon app.ico --hidden-import PIL._tkinter_finder --add-data "logo.png;." --add-data "app.ico;." --add-data "dist\EyeGuard.exe;." setup_ui.py
if errorlevel 1 goto failed

echo [5/5] Cleaning temporary build files...
rmdir /s /q build 2>nul
del /q EyeGuard.spec EyeGuard_Setup.spec 2>nul
if not exist "dist\EyeGuard_Setup.exe" goto failed

echo.
echo Build completed successfully.
echo Installer: dist\EyeGuard_Setup.exe
echo Portable:  dist\EyeGuard.portable.exe
echo.
pause
exit /b 0

:no_python
echo.
echo ERROR: Python 3 was not found on this computer.
echo Install Python 3 from https://www.python.org/downloads/windows/
echo During installation, enable the option: Add python.exe to PATH.
echo Then close this window, open a new Command Prompt, and run build.bat again.
echo.
pause
exit /b 1

:failed
echo.
echo ERROR: Build failed. Read the error messages above.
echo.
pause
exit /b 1
