# Changelog

All notable changes to this project will be documented in this file.

---

## [1.0] - 2026-05-21

### Changed
- **Complete UI redesign**: Converted from menu bar app (rumps) to native macOS window-based desktop application
- Replaced rumps library with PyQt6 for modern, professional UI
- Installation method changed: now uses native macOS `.app` bundle with PyInstaller, no longer requires manual Python environment setup
- Distribution format: now available as `.dmg` installer for easy drag-and-drop installation

### Added
- Full interactive window with status panel, controls, and live log display
- Real-time log viewer showing last 50 lines of sync activity
- "Copy Log" button for easy debugging and troubleshooting
- Visual status indicators: sync state, bookmark counts, history timestamps
- Configurable auto-sync interval selector (5 min – 2 hrs) with live updates
- Tools menu with options to open config, backups, debug info, and reset sync state
- Native macOS LaunchAgent for auto-launch on login with new installation script

### Fixed
- Removed menu bar visual clutter — single dedicated application window
- Improved user experience with clearer status information and log access

### Removed
- Menu bar app (`rumps` library) — replaced by desktop window app
- Old `menubar_app.py` and `install_menubar.sh` — replaced by PyInstaller approach

### Technical
- PyInstaller configuration (`safari_chrome_sync.spec`) for creating native `.app` bundle
- DMG builder script (`build_dmg.sh`) for distribution
- Updated dependencies: PyQt6, PyInstaller (removed rumps dependency)
- Sync engine (`safari_chrome_sync.py`) unchanged — maintained for backward compatibility

---

## [0.2] - 2026-03-29

### Fixed
- Install script now uses `launchctl bootstrap` instead of the deprecated `launchctl load`, which caused a "Load failed: Input/output error" on newer macOS versions

### Changed
- First-time sync procedure simplified: instead of temporarily disabling Google Sync, users now delete all Chrome bookmarks manually before the first sync — this is more reliable and prevents Google Sync from restoring old bookmarks
- Removed internal `post_first_run_cleanup` logic (no longer needed with the new first-time procedure)

### Documentation
- README updated with clearer first-time sync instructions
- Added recommended workflow for syncing Chrome (Windows) changes to Safari
- Added note that Terminal / iTerm does not need to stay open after installation
- Added explanation of when periodic background sync is useful

---

## [0.1] - 2026-03-28

### Initial release
- Menu bar app (`↔`) for macOS with automatic sync at a configurable interval (5 min – 2 hrs)
- First sync: all Chrome bookmarks and history are replaced with Safari data
- Subsequent syncs: bidirectional — additions and deletions synced in both directions
- Safari folder structure preserved 1-to-1 in Chrome
- Automatic backups before every sync
- Support for Google Sync: Safari bookmarks become available on Chrome on other devices (e.g. Windows PC)
