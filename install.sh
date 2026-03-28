#!/bin/bash
# ────────────────────────────────────────────────────────────────
# Safari ↔ Chrome Sync — Installatie & periodieke planning
# Maakt een macOS LaunchAgent aan die de sync automatisch uitvoert
# ────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$SCRIPT_DIR/safari_chrome_sync.py"
PLIST_LABEL="com.safari-chrome-sync"
PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_LABEL.plist"
LOG_PATH="$HOME/.safari_chrome_sync/sync.log"
CONFIG_PATH="$HOME/.safari_chrome_sync/config.json"

# ── Controleer vereisten ─────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "FOUT: python3 niet gevonden. Installeer Python 3 via https://python.org"
    exit 1
fi

PYTHON_VERSION=$(python3 -c "import sys; print(sys.version_info.minor)")
if [ "$PYTHON_VERSION" -lt 9 ]; then
    echo "FOUT: Python 3.9 of hoger vereist (gevonden: 3.$PYTHON_VERSION)"
    exit 1
fi

if [ ! -f "$SCRIPT" ]; then
    echo "FOUT: Script niet gevonden op: $SCRIPT"
    exit 1
fi

# ── Lees interval uit config (of gebruik standaard 30 min) ──────
INTERVAL_MINUTES=30
if [ -f "$CONFIG_PATH" ]; then
    INTERVAL_MINUTES=$(python3 -c "
import json, sys
try:
    cfg = json.load(open('$CONFIG_PATH'))
    print(cfg.get('interval_minutes', 30))
except Exception:
    print(30)
")
fi
INTERVAL_SECONDS=$((INTERVAL_MINUTES * 60))

echo ""
echo "Safari ↔ Chrome Sync — Installatie"
echo "═══════════════════════════════════"
echo "Script:   $SCRIPT"
echo "Interval: $INTERVAL_MINUTES minuten ($INTERVAL_SECONDS seconden)"
echo "Plist:    $PLIST_PATH"
echo "Log:      $LOG_PATH"
echo ""

# ── Maak LaunchAgents-map aan indien nodig ───────────────────────
mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/.safari_chrome_sync"

# ── Laad bestaande agent uit indien actief ───────────────────────
if launchctl list "$PLIST_LABEL" &>/dev/null 2>&1; then
    echo "Bestaande LaunchAgent uitladen..."
    launchctl unload "$PLIST_PATH" 2>/dev/null || true
fi

# ── Schrijf launchd plist ────────────────────────────────────────
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
        <string>/usr/bin/python3</string>
        <string>${SCRIPT}</string>
        <string>sync</string>
    </array>

    <!-- Herhaal elke N seconden -->
    <key>StartInterval</key>
    <integer>${INTERVAL_SECONDS}</integer>

    <!-- Niet direct uitvoeren bij laden -->
    <key>RunAtLoad</key>
    <false/>

    <!-- Log stdout en stderr naar hetzelfde bestand -->
    <key>StandardOutPath</key>
    <string>${LOG_PATH}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_PATH}</string>

    <!-- Herstart automatisch bij crashes -->
    <key>KeepAlive</key>
    <false/>
</dict>
</plist>
EOF

# ── Laad de agent in ─────────────────────────────────────────────
launchctl load "$PLIST_PATH"

echo "✓ LaunchAgent geïnstalleerd en geladen"
echo ""
echo "Gebruik:"
echo "──────────────────────────────────────────────────"
echo "  Sync nu uitvoeren:"
echo "    python3 \"$SCRIPT\" sync"
echo ""
echo "  Status bekijken:"
echo "    python3 \"$SCRIPT\" status"
echo ""
echo "  Interval wijzigen (bijv. 15 minuten):"
echo "    python3 \"$SCRIPT\" config --interval 15"
echo "    bash \"$0\"   ← installeer opnieuw om interval door te voeren"
echo ""
echo "  Geschiedenis-sync uitschakelen:"
echo "    python3 \"$SCRIPT\" config --no-history"
echo ""
echo "  Automatische sync uitschakelen:"
echo "    launchctl unload \"$PLIST_PATH\""
echo ""
echo "  Automatische sync opnieuw inschakelen:"
echo "    launchctl load \"$PLIST_PATH\""
echo ""
echo "  Staat resetten (volgende sync = eerste run):"
echo "    python3 \"$SCRIPT\" reset"
echo ""
echo "  Logbestand bekijken:"
echo "    tail -f \"$LOG_PATH\""
echo ""
echo "LET OP: Geef Terminal (of Python) Volledige Schijftoegang voor toegang"
echo "tot Safari-bestanden:"
echo "  Systeeminstellingen → Privacy en beveiliging → Volledige schijftoegang"
echo "──────────────────────────────────────────────────"
echo ""
