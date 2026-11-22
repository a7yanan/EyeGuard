@echo off
REM Runs EyeGuard from the source code (no build needed). Use it while you are changing the program.
cd /d "%~dp0"
python -c "import PIL" 2>nul || python -m pip install Pillow
start "" pythonw "%~dp0eyeguard.py"
