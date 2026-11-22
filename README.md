# EyeGuard

Protects your eyes from screen light with a warm color filter and eye-movement reminders.

## Run from Source
```bat
run.bat
```

## Build the Executables
```bat
build.bat
```
The build produces:
- `dist\EyeGuard.exe` — the application
- `dist\EyeGuard.portable.exe` — same binary (copy), useful for silent auto-update
- `dist\EyeGuard_Setup.exe` — the installer

## Automatic Updates (GitHub Releases)

Repository: https://github.com/a7yanan/EyeGuard

1. Build the project using `build.bat`.
2. Create a new Release with a tag in the format `vX.Y.Z`. Make sure the `APP_VERSION` value in `eyeguard.py` and `setup_ui.py` matches the release tag (without the leading `v`).
3. Attach **at least one** of the following assets (the updater picks the best available):

   **Preferred for silent in-place update**
   - `EyeGuard.portable.exe` (or `EyeGuard.exe`)

   **Also accepted**
   - Any installer named like `EyeGuard_Setup.exe`, `EyeGuard_Setupv1.0.1.exe`, `EyeGuard_Setup_v1.0.1.exe`, etc.

4. You no longer *must* upload the portable build. If only a Setup installer is present, the app will download it and launch it (UAC prompt). If a portable EXE is present it is preferred and replaces the running binary silently after elevation.

The application checks GitHub for a newer release every 24 hours. You can also start a check manually from Settings.

> First-time installs should use the Setup. Automatic updates work with either the portable EXE or the Setup installer.

## Requirements
- Windows 10/11
- Python 3 and Pillow (for development and building)
