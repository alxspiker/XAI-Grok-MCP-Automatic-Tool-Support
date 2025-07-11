@echo off
setlocal

echo Checking for Python...
python --version >nul 2>&1 || (
    echo Python is not installed or not in PATH.
    pause
    exit /b 1
)

echo Installing PyInstaller if not found...
python -m pip install --upgrade pip
python -m pip install pyinstaller

echo Building executable with PyInstaller...
pyinstaller --onefile main.py

echo.
echo Build complete. Check the "dist" folder for the EXE.
pause
