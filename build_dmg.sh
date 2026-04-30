#!/bin/bash
# Build a standalone Draft Advisor .dmg for macOS.
# Run from the project root: ./build_dmg.sh
set -e

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo "==> Step 1: Bundle Python server with PyInstaller"
venv/bin/pyinstaller web_server.spec --distpath dist --workpath build/pyinstaller --noconfirm

echo ""
echo "==> Step 2: Package Electron app + server into .dmg"
cd electron
npm run build

echo ""
echo "Done! Find the .dmg in dist/"
ls -lh "$DIR/dist/"*.dmg 2>/dev/null || true
