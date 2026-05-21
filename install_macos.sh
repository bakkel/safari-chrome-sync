#!/bin/bash
#
# Safari ↔ Chrome Sync — macOS Installation Script
#
# Install as background app with auto-launch on login
#

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PYTHON_BIN="$(command -v python3)"

if [ -z "$PYTHON_BIN" ]; then
    echo "Error: python3 not found. Install Python 3.9+ first."
    exit 1
fi

PYTHON_VERSION=$("$PYTHON_BIN" --version 2>&1 | awk '{print $2}')
echo "Found Python: $PYTHON_VERSION"

# Check Python 3.9+
PYTHON_MAJOR=$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.major)')
PYTHON_MINOR=$("$PYTHON_BIN" -c 'import sys; print(sys.version_info.minor)')
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 9 ]); then
    echo "Error: Python 3.9+ required, found $PYTHON_MAJOR.$PYTHON_MINOR"
    exit 1
fi

echo "✓ Python version OK"
echo ""

# Install dependencies
echo "Installing dependencies..."
"$PYTHON_BIN" -m pip install --quiet --upgrade pip
"$PYTHON_BIN" -m pip install -r "$SCRIPT_DIR/requirements.txt" > /dev/null 2>&1
echo "✓ Dependencies installed"
echo ""

# Create plist file for LaunchAgent
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="$PLIST_DIR/com.safari-chrome-sync.plist"

# Remove old plist if it exists (from older install)
if [ -f "$PLIST_DIR/com.safari-chrome-sync-menubar.plist" ]; then
    echo "Removing old LaunchAgent..."
    launchctl unload "$PLIST_DIR/com.safari-chrome-sync-menubar.plist" 2>/dev/null || true
    rm -f "$PLIST_DIR/com.safari-chrome-sync-menubar.plist"
fi

# Create new LaunchAgent plist
mkdir -p "$PLIST_DIR"
cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.safari-chrome-sync</string>

    <key>ProgramArguments</key>
    <array>
        <string>$PYTHON_BIN</string>
        <string>$SCRIPT_DIR/app_window.py</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <key>ProcessType</key>
    <string>Interactive</string>

    <key>StandardOutPath</key>
    <string>$HOME/.safari_chrome_sync/sync.log</string>

    <key>StandardErrorPath</key>
    <string>$HOME/.safari_chrome_sync/sync.log</string>
</dict>
</plist>
EOF

chmod 644 "$PLIST_FILE"
echo "✓ LaunchAgent plist created: $PLIST_FILE"
echo ""

# Load the LaunchAgent
echo "Loading LaunchAgent..."
launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE" 2>/dev/null || true
echo "✓ LaunchAgent loaded"
echo ""

# Full Disk Access instructions
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⚠️  IMPORTANT: Grant Full Disk Access to Python"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "The app needs Full Disk Access to read Safari bookmarks and history."
echo ""
echo "1. Open System Settings → Privacy & Security → Full Disk Access"
echo "2. Click + and navigate to:"
echo "   /Library/Frameworks/Python.framework/Versions"
echo "3. Select your Python version → Resources → Python.app"
echo "4. Also add Terminal if not listed"
echo "5. Restart Terminal or log out and back in"
echo ""
echo "Without this, the sync will fail with permission errors."
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "✓ Installation complete!"
echo ""
echo "The app will start automatically after you:"
echo "  - Restart Terminal, or"
echo "  - Log out and log back in"
echo ""
echo "To start manually now:"
echo "  $PYTHON_BIN $SCRIPT_DIR/app_window.py"
echo ""
