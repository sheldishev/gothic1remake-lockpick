@echo off
setlocal
cd /d "%~dp0"

python -c "import PyInstaller" 2>nul || (
  echo Installing PyInstaller...
  python -m pip install pyinstaller
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist

python -m PyInstaller --noconfirm PlatePuzzle.spec

echo.
echo Done: dist\PlatePuzzle.exe
pause
