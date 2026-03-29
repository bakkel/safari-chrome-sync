#!/usr/bin/env python3
"""
Safari ↔ Chrome Sync — macOS Menu Bar App

Requirements:
  pip install rumps

Start:
  python3 menubar_app.py

Auto-start at login:
  bash install_menubar.sh
"""

try:
    import rumps
except ImportError:
    import sys
    print("rumps not found. Install with: pip install rumps")
    sys.exit(1)

import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

# Add script directory so safari_chrome_sync is importable
sys.path.insert(0, str(Path(__file__).parent))
import safari_chrome_sync as _sync

SYNC_DIR    = Path.home() / ".safari_chrome_sync"
CONFIG_FILE = SYNC_DIR / "config.json"
STATE_FILE  = SYNC_DIR / "state.json"
LOG_FILE    = SYNC_DIR / "sync.log"
SCRIPT      = Path(__file__).parent / "safari_chrome_sync.py"

INTERVALS = [5, 10, 15, 30, 60, 120]
INTERVAL_LABELS = {
    5: "5 minutes", 10: "10 minutes", 15: "15 minutes",
    30: "30 minutes", 60: "1 hour", 120: "2 hours",
}

ICON_IDLE   = "↔"
ICON_BUSY   = "⟳"
ICON_ERROR  = "↔!"


class SyncApp(rumps.App):

    def __init__(self):
        super().__init__(ICON_IDLE, quit_button=None)
        self._syncing    = False
        self._auto_timer = None
        self._last_error = None

        SYNC_DIR.mkdir(parents=True, exist_ok=True)
        _sync.setup_logging(verbose=False)

        self._build_menu()
        self._refresh_status()
        self._reschedule()

    # ── Config / State helpers ────────────────────────────────────────────────
    def _cfg(self) -> dict:
        if CONFIG_FILE.exists():
            try:
                return {**_sync.DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text())}
            except Exception:
                pass
        return _sync.DEFAULT_CONFIG.copy()

    def _state(self) -> dict:
        if STATE_FILE.exists():
            try:
                return json.loads(STATE_FILE.read_text())
            except Exception:
                pass
        return {}

    # ── Build menu ────────────────────────────────────────────────────────────
    def _build_menu(self):
        cfg = self._cfg()

        # ── Status line (read-only) ───────────────────────────────────────────
        self._status_item = rumps.MenuItem("Last sync: never")
        self._status_item.set_callback(None)

        # ── Sync now ──────────────────────────────────────────────────────────
        sync_now = rumps.MenuItem("Sync now", callback=self._on_sync_now)

        # ── Interval submenu ──────────────────────────────────────────────────
        interval_menu = rumps.MenuItem("Interval")
        self._interval_items = {}
        current = cfg.get("interval_minutes", 30)
        for m, label in INTERVAL_LABELS.items():
            item = rumps.MenuItem(label, callback=self._make_interval_cb(m))
            item.state = 1 if m == current else 0
            interval_menu.add(item)
            self._interval_items[m] = item

        # ── Toggles ───────────────────────────────────────────────────────────
        self._bm_item = rumps.MenuItem(
            "Sync bookmarks", callback=self._toggle_bookmarks
        )
        self._bm_item.state = 1 if cfg.get("sync_bookmarks") else 0

        self._hist_item = rumps.MenuItem(
            "Sync history", callback=self._toggle_history
        )
        self._hist_item.state = 1 if cfg.get("sync_history") else 0

        # ── Other options ─────────────────────────────────────────────────────
        log_item   = rumps.MenuItem("Open log file",             callback=self._open_log)
        back_item  = rumps.MenuItem("Open backup folder",        callback=self._open_backups)
        debug_item = rumps.MenuItem("Debug: dump Safari structure", callback=self._on_debug)
        reset_item = rumps.MenuItem("Reset (new first run)",     callback=self._on_reset)
        quit_item  = rumps.MenuItem("Quit",                      callback=rumps.quit_application)

        self.menu = [
            self._status_item,
            None,
            sync_now,
            None,
            interval_menu,
            None,
            self._bm_item,
            self._hist_item,
            None,
            log_item,
            back_item,
            debug_item,
            reset_item,
            None,
            quit_item,
        ]

    # ── Refresh status ────────────────────────────────────────────────────────
    def _refresh_status(self):
        state = self._state()
        last  = state.get("last_sync")
        if self._syncing:
            self._status_item.title = "Syncing…"
            return
        if self._last_error:
            self._status_item.title = f"Error: {self._last_error[:60]}"
            return
        if last:
            try:
                dt = datetime.fromisoformat(last)
                label = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                label = str(last)
            n_safari = len(state.get("safari_bookmark_urls", []))
            n_chrome = len(state.get("chrome_bookmark_urls", []))
            self._status_item.title = (
                f"Last sync: {label}  "
                f"(S:{n_safari} C:{n_chrome})"
            )
        else:
            self._status_item.title = "Last sync: never — click to start"

    # ── Interval helpers ──────────────────────────────────────────────────────
    def _make_interval_cb(self, minutes: int):
        def cb(sender):
            cfg = self._cfg()
            cfg["interval_minutes"] = minutes
            _sync.save_config(cfg)
            for m, item in self._interval_items.items():
                item.state = 1 if m == minutes else 0
            self._reschedule()
        return cb

    def _reschedule(self):
        """Reschedule the automatic sync timer."""
        if self._auto_timer:
            self._auto_timer.cancel()
        seconds = self._cfg().get("interval_minutes", 30) * 60
        self._auto_timer = threading.Timer(seconds, self._auto_sync)
        self._auto_timer.daemon = True
        self._auto_timer.start()

    # ── Run sync ──────────────────────────────────────────────────────────────
    def _on_sync_now(self, _sender):
        if self._syncing:
            return
        threading.Thread(target=self._run_sync, kwargs={"manual": True}, daemon=True).start()

    def _auto_sync(self):
        self._run_sync(manual=False)
        self._reschedule()

    def _run_sync(self, manual: bool = False):
        if self._syncing:
            return
        self._syncing    = True
        self._last_error = None
        self.title       = ICON_BUSY
        self._refresh_status()

        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "sync"],
                capture_output=True, text=True, timeout=180
            )
            if result.returncode == 0:
                self._last_error = None
                self.title = ICON_IDLE
                if manual:
                    state = self._state()
                    n_s = len(state.get("safari_bookmark_urls", []))
                    n_c = len(state.get("chrome_bookmark_urls", []))
                    rumps.notification(
                        "Safari ↔ Chrome Sync",
                        "Sync complete",
                        f"Bookmarks — Safari: {n_s}  Chrome: {n_c}",
                        sound=False,
                    )
            else:
                err = (result.stderr or result.stdout or "Unknown error").strip()
                self._last_error = err.splitlines()[0][:80] if err else "Error"
                self.title = ICON_ERROR
                rumps.notification(
                    "Safari ↔ Chrome Sync",
                    "Sync failed",
                    self._last_error,
                    sound=True,
                )
        except subprocess.TimeoutExpired:
            self._last_error = "Timeout (>3 min)"
            self.title = ICON_ERROR
            rumps.notification(
                "Safari ↔ Chrome Sync", "Timeout",
                "Sync took too long. Check the log file.",
                sound=True,
            )
        except Exception as exc:
            self._last_error = str(exc)[:80]
            self.title = ICON_ERROR
        finally:
            self._syncing = False
            self._refresh_status()

    # ── Toggle callbacks ──────────────────────────────────────────────────────
    def _toggle_bookmarks(self, sender):
        cfg = self._cfg()
        cfg["sync_bookmarks"] = not cfg.get("sync_bookmarks", True)
        _sync.save_config(cfg)
        sender.state = 1 if cfg["sync_bookmarks"] else 0

    def _toggle_history(self, sender):
        cfg = self._cfg()
        cfg["sync_history"] = not cfg.get("sync_history", True)
        _sync.save_config(cfg)
        sender.state = 1 if cfg["sync_history"] else 0

    # ── Other callbacks ───────────────────────────────────────────────────────
    def _open_log(self, _sender):
        if LOG_FILE.exists():
            subprocess.run(["open", "-a", "Console", str(LOG_FILE)])
        else:
            rumps.alert(
                title="No log file",
                message="No log file has been created yet. Run a sync first.",
            )

    def _open_backups(self, _sender):
        backup_dir = SYNC_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(backup_dir)])

    def _on_debug(self, _sender):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "debug"],
            capture_output=True, text=True, timeout=30
        )
        debug_file = SYNC_DIR / "debug_safari.txt"
        if debug_file.exists():
            subprocess.run(["open", "-t", str(debug_file)])
        else:
            rumps.alert("Debug failed", result.stderr or result.stdout or "Unknown error")

    def _on_reset(self, _sender):
        import subprocess as _sp
        chrome_open = _sp.run(["pgrep", "-x", "Google Chrome"], capture_output=True).returncode == 0
        safari_open = _sp.run(["pgrep", "-x", "Safari"],        capture_output=True).returncode == 0

        warnings = ""
        if chrome_open:
            warnings += "\n\n⚠️  Chrome is open — close Chrome FIRST, otherwise bookmarks will not be overwritten correctly."
        if safari_open:
            warnings += "\n\n⚠️  Safari is open — close Safari FIRST for the Chrome→Safari direction."

        response = rumps.alert(
            title="Reset sync state?",
            message=(
                "The next sync will be treated as a first run:\n"
                "all Chrome bookmarks and history will be overwritten "
                "with Safari data." + warnings + "\n\nContinue?"
            ),
            ok="Reset",
            cancel="Cancel",
        )
        if response == 1:
            if STATE_FILE.exists():
                STATE_FILE.unlink()
            self._refresh_status()
            msg = "Close Chrome and Safari, then click 'Sync now'." if (chrome_open or safari_open) else "Click 'Sync now'."
            rumps.notification(
                "Safari ↔ Chrome Sync",
                "State reset",
                msg,
                sound=False,
            )


if __name__ == "__main__":
    SyncApp().run()
