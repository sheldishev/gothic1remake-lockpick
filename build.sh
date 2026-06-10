#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if ! python3 -c "import PyInstaller" 2>/dev/null; then
  echo "Установка PyInstaller…"
  python3 -m pip install --user pyinstaller
fi

rm -rf build
rm -f dist/PlatePuzzle dist/PlatePuzzle.exe
rm -rf dist/PlatePuzzle.app dist/PlatePuzzle
python3 -m PyInstaller --noconfirm PlatePuzzle.spec

echo ""
echo "Готово: dist/PlatePuzzle"
echo "Запуск: ./dist/PlatePuzzle"
