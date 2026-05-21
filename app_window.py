#!/usr/bin/env python3
"""
Safari ↔ Chrome Sync — macOS Desktop Application (PyQt6)

Features:
- Main window with sync status and controls
- Real-time log display
- Auto-sync scheduling with configurable interval
- Native macOS notifications
"""

import json
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path

# Import sync engine
sys.path.insert(0, str(Path(__file__).parent))
import safari_chrome_sync as _sync

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QComboBox, QCheckBox, QLabel, QTextEdit, QGroupBox,
        QMenuBar, QMenu, QMessageBox
    )
    from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
    from PyQt6.QtGui import QFont, QIcon
except ImportError:
    print("PyQt6 not found. Install with: pip install PyQt6")
    sys.exit(1)

# Paths
SYNC_DIR = Path.home() / ".safari_chrome_sync"
CONFIG_FILE = SYNC_DIR / "config.json"
STATE_FILE = SYNC_DIR / "state.json"
LOG_FILE = SYNC_DIR / "sync.log"
SCRIPT = Path(__file__).parent / "safari_chrome_sync.py"

INTERVALS = [5, 10, 15, 30, 60, 120]


class SyncWorkerThread(QThread):
    """Background thread to run sync subprocess without blocking UI."""
    finished = pyqtSignal(int, str)  # returncode, stderr_text

    def __init__(self, script_path):
        super().__init__()
        self.script_path = script_path

    def run(self):
        try:
            result = subprocess.run(
                [sys.executable, str(self.script_path), "sync"],
                capture_output=True, text=True, timeout=180
            )
            err = result.stderr or ""
            self.finished.emit(result.returncode, err)
        except subprocess.TimeoutExpired:
            self.finished.emit(1, "Timeout: sync took longer than 3 minutes")
        except Exception as e:
            self.finished.emit(1, str(e))


class SyncApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Safari ↔ Chrome Sync")
        self.setGeometry(100, 100, 700, 600)

        SYNC_DIR.mkdir(parents=True, exist_ok=True)
        _sync.setup_logging(verbose=False)

        self._syncing = False
        self._last_error = None
        self._auto_timer = None
        self._sync_thread = None

        self._build_ui()
        self._build_menu()
        self._refresh_status()
        self._reschedule()

    # ── Config & State ────────────────────────────────────────────────────
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

    # ── Build UI ──────────────────────────────────────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(12)
        layout.setContentsMargins(16, 16, 16, 16)

        # ── Status Group ──────────────────────────────────────────────────
        status_group = QGroupBox("Status")
        status_layout = QVBoxLayout()

        self._status_label = QLabel("Preparing...")
        status_layout.addWidget(self._status_label)

        self._bookmarks_label = QLabel()
        status_layout.addWidget(self._bookmarks_label)

        self._history_label = QLabel()
        status_layout.addWidget(self._history_label)

        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # ── Controls Group ────────────────────────────────────────────────
        control_group = QGroupBox("Controls")
        control_layout = QVBoxLayout()

        # Sync button
        button_layout = QHBoxLayout()
        self._sync_button = QPushButton("Sync Now")
        self._sync_button.clicked.connect(self._on_sync_now)
        button_layout.addWidget(self._sync_button)
        button_layout.addStretch()
        control_layout.addLayout(button_layout)

        # Interval selector
        interval_layout = QHBoxLayout()
        interval_label = QLabel("Auto-sync interval:")
        self._interval_combo = QComboBox()
        cfg = self._cfg()
        current = cfg.get("interval_minutes", 30)
        for m in INTERVALS:
            label = f"{m} minutes" if m < 60 else f"{m // 60} hour(s)"
            self._interval_combo.addItem(label, m)
            if m == current:
                self._interval_combo.setCurrentIndex(self._interval_combo.count() - 1)
        self._interval_combo.currentIndexChanged.connect(self._on_interval_changed)
        interval_layout.addWidget(interval_label)
        interval_layout.addWidget(self._interval_combo)
        interval_layout.addStretch()
        control_layout.addLayout(interval_layout)

        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # ── Toggles Group ─────────────────────────────────────────────────
        toggle_group = QGroupBox("Options")
        toggle_layout = QVBoxLayout()

        self._bm_check = QCheckBox("Sync bookmarks")
        self._bm_check.setChecked(cfg.get("sync_bookmarks", True))
        self._bm_check.stateChanged.connect(self._on_toggle_bookmarks)
        toggle_layout.addWidget(self._bm_check)

        self._hist_check = QCheckBox("Sync history")
        self._hist_check.setChecked(cfg.get("sync_history", True))
        self._hist_check.stateChanged.connect(self._on_toggle_history)
        toggle_layout.addWidget(self._hist_check)

        toggle_group.setLayout(toggle_layout)
        layout.addWidget(toggle_group)

        # ── Log View ──────────────────────────────────────────────────────
        log_group = QGroupBox("Log")
        log_layout = QVBoxLayout()

        self._log_view = QTextEdit()
        self._log_view.setReadOnly(True)
        self._log_view.setMaximumHeight(200)
        font = QFont("Courier")
        font.setPointSize(9)
        self._log_view.setFont(font)
        log_layout.addWidget(self._log_view)

        # Copy log button
        log_button_layout = QHBoxLayout()
        copy_btn = QPushButton("Copy Log")
        copy_btn.clicked.connect(self._copy_log)
        log_button_layout.addStretch()
        log_button_layout.addWidget(copy_btn)
        log_layout.addLayout(log_button_layout)

        log_group.setLayout(log_layout)
        layout.addWidget(log_group)

        # Start log tail timer
        self._log_timer = QTimer()
        self._log_timer.timeout.connect(self._update_log)
        self._log_timer.start(500)  # Update every 500ms

    # ── Build Menu ────────────────────────────────────────────────────────
    def _build_menu(self):
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("File")
        quit_action = file_menu.addAction("Quit")
        quit_action.triggered.connect(self.close)

        # Tools menu
        tools_menu = menubar.addMenu("Tools")

        config_action = tools_menu.addAction("Open Config")
        config_action.triggered.connect(self._open_config)

        backup_action = tools_menu.addAction("Open Backups")
        backup_action.triggered.connect(self._open_backups)

        debug_action = tools_menu.addAction("Debug: Dump Safari Structure")
        debug_action.triggered.connect(self._on_debug)

        tools_menu.addSeparator()

        reset_action = tools_menu.addAction("Reset Sync State")
        reset_action.triggered.connect(self._on_reset)

    # ── Status Updates ────────────────────────────────────────────────────
    def _refresh_status(self):
        state = self._state()
        cfg = self._cfg()

        # Status line
        if self._syncing:
            status_text = "Syncing…"
        elif self._last_error:
            status_text = f"Error: {self._last_error[:80]}"
        else:
            last = state.get("last_sync")
            if last:
                try:
                    dt = datetime.fromisoformat(last)
                    label = dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    label = str(last)
                status_text = f"Last sync: {label}"
            else:
                status_text = "Last sync: never"

        self._status_label.setText(status_text)

        # Bookmark counts
        n_safari = len(state.get("safari_bookmark_urls", []))
        n_chrome = len(state.get("chrome_bookmark_urls", []))
        self._bookmarks_label.setText(f"Bookmarks — Safari: {n_safari}  ↔  Chrome: {n_chrome}")

        # History timestamps
        last_s = state.get("last_safari_history_unix", 0.0)
        last_c = state.get("last_chrome_history_unix", 0.0)
        fmt = lambda ts: datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "never"
        self._history_label.setText(f"History synced — Safari: {fmt(last_s)}  |  Chrome: {fmt(last_c)}")

        # Update button state
        self._sync_button.setEnabled(not self._syncing)

    def _update_log(self):
        """Read last 50 lines from log file and display in text view."""
        if not LOG_FILE.exists():
            return
        try:
            with open(LOG_FILE, 'r') as f:
                lines = f.readlines()
            # Show last 50 lines
            recent = lines[-50:]
            self._log_view.setPlainText(''.join(recent))
            # Scroll to bottom
            self._log_view.verticalScrollBar().setValue(
                self._log_view.verticalScrollBar().maximum()
            )
        except Exception:
            pass

    def _copy_log(self):
        """Copy log text to clipboard."""
        text = self._log_view.toPlainText()
        if text:
            QApplication.clipboard().setText(text)
            QMessageBox.information(self, "Copied", "Log copied to clipboard!")
        else:
            QMessageBox.information(self, "Empty", "Nothing to copy.")

    # ── Sync Operations ──────────────────────────────────────────────────
    def _on_sync_now(self, _checked=False):
        if self._syncing:
            return

        self._syncing = True
        self._last_error = None
        self._refresh_status()

        self._sync_thread = SyncWorkerThread(SCRIPT)
        self._sync_thread.finished.connect(self._on_sync_finished)
        self._sync_thread.start()

    def _on_sync_finished(self, returncode, err_text):
        self._syncing = False
        self._refresh_status()

        if returncode == 0:
            self._last_error = None
            # Notification would go here (native macOS notification)
            print("Sync completed successfully")
        else:
            err = (err_text.strip() or "Unknown error").splitlines()[0][:80]
            self._last_error = err or "Sync failed"
            print(f"Sync failed: {self._last_error}")
            self._refresh_status()

    def _reschedule(self):
        """Set up auto-sync timer based on config interval."""
        if self._auto_timer:
            self._auto_timer.cancel()

        seconds = self._cfg().get("interval_minutes", 30) * 60
        self._auto_timer = threading.Timer(seconds, self._auto_sync)
        self._auto_timer.daemon = True
        self._auto_timer.start()

    def _auto_sync(self):
        """Auto-sync callback triggered by timer."""
        self._on_sync_now()
        self._reschedule()

    # ── Config & Toggle Callbacks ─────────────────────────────────────────
    def _on_interval_changed(self):
        minutes = self._interval_combo.currentData()
        if minutes is not None:
            cfg = self._cfg()
            cfg["interval_minutes"] = minutes
            _sync.save_config(cfg)
            self._reschedule()

    def _on_toggle_bookmarks(self):
        cfg = self._cfg()
        cfg["sync_bookmarks"] = self._bm_check.isChecked()
        _sync.save_config(cfg)

    def _on_toggle_history(self):
        cfg = self._cfg()
        cfg["sync_history"] = self._hist_check.isChecked()
        _sync.save_config(cfg)

    # ── Menu Actions ──────────────────────────────────────────────────────
    def _open_config(self):
        if CONFIG_FILE.exists():
            subprocess.run(["open", "-t", str(CONFIG_FILE)])
        else:
            QMessageBox.information(self, "No Config", "Config file not found. Run a sync first.")

    def _open_backups(self):
        backup_dir = SYNC_DIR / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["open", str(backup_dir)])

    def _on_debug(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "debug"],
            capture_output=True, text=True, timeout=30
        )
        debug_file = SYNC_DIR / "debug_safari.txt"
        if debug_file.exists():
            subprocess.run(["open", "-t", str(debug_file)])
        else:
            QMessageBox.critical(self, "Debug Failed", result.stderr or result.stdout or "Unknown error")

    def _on_reset(self):
        # Check if browsers are open
        chrome_open = subprocess.run(["pgrep", "-x", "Google Chrome"], capture_output=True).returncode == 0
        safari_open = subprocess.run(["pgrep", "-x", "Safari"], capture_output=True).returncode == 0

        warnings = ""
        if chrome_open:
            warnings += "\n\n⚠️  Chrome is open — close Chrome FIRST, otherwise bookmarks will not be overwritten correctly."
        if safari_open:
            warnings += "\n\n⚠️  Safari is open — close Safari FIRST for the Chrome→Safari direction."

        reply = QMessageBox.question(
            self,
            "Reset Sync State?",
            f"The next sync will treat as a first run:\n"
            f"all Chrome bookmarks and history will be\n"
            f"overwritten with Safari data.{warnings}\n\n"
            f"Continue?",
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel
        )

        if reply == QMessageBox.StandardButton.Ok:
            if STATE_FILE.exists():
                STATE_FILE.unlink()
            self._refresh_status()
            msg = "Close Chrome and Safari, then click 'Sync Now'." if (chrome_open or safari_open) else "Click 'Sync Now'."
            QMessageBox.information(self, "State Reset", msg)

    def closeEvent(self, event):
        """Clean up timers when app closes."""
        if self._auto_timer:
            self._auto_timer.cancel()
        if self._log_timer:
            self._log_timer.stop()
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SyncApp()
    window.show()
    sys.exit(app.exec())
