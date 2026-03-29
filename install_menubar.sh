#!/bin/bash
# ────────────────────────────────────────────────────────────────
# Safari ↔ Chrome Sync — Menubalk App Installatie
# Start de menubalk-app automatisch bij inloggen via LaunchAgent
# ────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_SCRIPT="$SCRIPT_DIR/menubar_app.py"
SYNC_SCRIPT="$SCRIPT_DIR/safari_chrome_sync.py"
PLIST_LABEL="com.safari-chrome-sync-menubar"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
LOG_PATH="$HOME/.safari_chrome_sync/sync.log"

# ── Controleer vereisten ─────────────────────────────────────────
echo ""
echo "Safari ↔ Chrome Sync — Menubalk App Installatie"
echo "═══════════════════════════════════════════════"

if ! command -v python3 &>/dev/null; then
    echo "FOUT: python3 niet gevonden."
    exit 1
fi

PYTHON_BIN="$(command -v python3)"
echo "Python:  $PYTHON_BIN"

# Controleer / installeer rumps
if ! python3 -c "import rumps" &>/dev/null; then
    echo "rumps niet gevonden — installeren..."
    pip3 install rumps --quiet
    echo "✓ rumps geïnstalleerd"
else
    RUMPS_VER=$(python3 -c "import rumps; print(rumps.__version__)")
    echo "rumps:   $RUMPS_VER (al geïnstalleerd)"
fi

if [ ! -f "$APP_SCRIPT" ]; then
    echo "FOUT: menubar_app.py niet gevonden op: $APP_SCRIPT"
    exit 1
fi

# ── Verwijder eventuele achtergrond-agent (install.sh versie) ────
OLD_PLIST="$HOME/Library/LaunchAgents/com.safari-chrome-sync.plist"
if [ -f "$OLD_PLIST" ]; then
    echo ""
    echo "Oude achtergrond-LaunchAgent gevonden — uitladen en verwijderen..."
    launchctl unload "$OLD_PLIST" 2>/dev/null || true
    rm "$OLD_PLIST"
    echo "✓ Oude agent verwijderd"
fi

# ── Verwijder bestaande menubalk-agent indien actief ────────────
if launchctl list "$PLIST_LABEL" &>/dev/null 2>&1; then
    echo "Bestaande menubalk-agent uitladen..."
    launchctl bootout "gui/$(id -u)/$PLIST_LABEL" 2>/dev/null || true
fi

# ── Maak mappen aan ──────────────────────────────────────────────
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/.safari_chrome_sync"

# ── Schrijf LaunchAgent plist ────────────────────────────────────
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_LABEL}</string>

    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_BIN}</string>
        <string>${APP_SCRIPT}</string>
    </array>

    <!-- Direct starten bij laden (= bij inloggen) -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Herstart bij afsluiten (tenzij de gebruiker afsluit via het menu) -->
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>

    <!-- GUI-app: toegang tot Aqua-sessie vereist -->
    <key>ProcessType</key>
    <string>Interactive</string>

    <key>StandardOutPath</key>
    <string>${LOG_PATH}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_PATH}</string>
</dict>
</plist>
EOF

# ── Laad de agent in ─────────────────────────────────────────────
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"

echo ""
echo "✓ Menubalk-app geïnstalleerd en gestart"
echo "  Plist: $PLIST_PATH"
echo ""
echo "De app ↔ verschijnt nu in je menubalk."
echo ""
echo "Handige commando's:"
echo "──────────────────────────────────────────────────"
echo "  App nu starten (zonder herinstalleren):"
echo "    python3 \"$APP_SCRIPT\" &"
echo ""
echo "  App stoppen:"
echo "    launchctl bootout \"gui/$(id -u)/com.safari-chrome-sync-menubar\""
echo ""
echo "  App opnieuw inschakelen bij inloggen:"
echo "    launchctl bootstrap \"gui/$(id -u)\" \"$PLIST_PATH\""
echo ""
echo "  Logbestand bekijken:"
echo "    tail -f \"$LOG_PATH\""
echo ""
echo "LET OP: Geef Terminal (of Python) Volledige Schijftoegang:"
echo "  Systeeminstellingen → Privacy en beveiliging → Volledige schijftoegang"
echo "──────────────────────────────────────────────────"
echo ""
