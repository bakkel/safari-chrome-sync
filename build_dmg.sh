#!/bin/bash
#
# Build DMG installer for Safari ↔ Chrome Sync
#
# Requires: create-dmg tool (brew install create-dmg)
#
# Usage: bash build_dmg.sh
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
APP_NAME="Safari Chrome Sync"
DMG_NAME="Safari Chrome Sync.dmg"
APP_PATH="$SCRIPT_DIR/dist/$APP_NAME.app"
DMG_PATH="$SCRIPT_DIR/$DMG_NAME"

# Check if .app bundle exists
if [ ! -d "$APP_PATH" ]; then
    echo "Error: $APP_NAME.app not found"
    echo "Run 'pyinstaller safari_chrome_sync.spec' first"
    exit 1
fi

echo "Creating DMG installer..."
echo "  Source: $APP_PATH"
echo "  Output: $DMG_PATH"
echo ""

# Remove old DMG if it exists
rm -f "$DMG_PATH"

# Check if create-dmg is installed
if ! command -v create-dmg &> /dev/null; then
    echo "create-dmg not found. Install with: brew install create-dmg"
    exit 1
fi

# Create DMG using create-dmg tool
create-dmg \
    --volname "$APP_NAME" \
    --window-pos 200 120 \
    --window-size 600 400 \
    --app-drop-link 400 200 \
    --icon "$APP_NAME.app" 200 200 \
    "$DMG_PATH" \
    "$SCRIPT_DIR/dist/$APP_NAME.app"

echo ""
echo "✓ DMG created successfully: $DMG_PATH"
echo ""
echo "To distribute:"
echo "  - Upload $DMG_NAME to GitHub releases"
echo "  - Users download and double-click to mount"
echo "  - Drag $APP_NAME.app to /Applications"
