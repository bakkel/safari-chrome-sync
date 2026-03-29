# Changelog

All notable changes to this project will be documented in this file.

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
