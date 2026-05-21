# safari-chrome-sync

A native macOS desktop application that automatically synchronizes bookmarks and browsing history between Safari and Google Chrome. Because Chrome uses Google Sync, your Safari bookmarks will also become available on Chrome on other devices — such as a Windows PC.

> **About this project**
> This tool was created by **Michel van Helden**, a non-developer, entirely with the help of [Claude](https://claude.ai) (Anthropic's AI assistant). No prior programming knowledge was required. If you find a bug or have a feature request, please open a [GitHub Issue](https://github.com/bakkel/safari-chrome-sync/issues) — feedback is always welcome.

---

## Features

- **Interactive window** with sync controls, status display, and live activity log
- **First sync**: all Chrome bookmarks and history are completely replaced by Safari data
- **Subsequent syncs**: bidirectional — additions and deletions are kept in sync in both browsers
- **Safari's full folder structure** is preserved 1-to-1 in Chrome
- **Auto-sync scheduling**: configurable interval (5 min – 2 hrs)
- **Real-time log viewer** showing last 50 lines of sync activity — copy to clipboard for debugging
- **Easy installation**: native `.dmg` installer, no Python setup required
- **Auto-launch on login** via macOS LaunchAgent

---

## Requirements

- macOS with Safari and Google Chrome installed
- Full Disk Access for Safari Chrome Sync (see Step 2 below)

---

## Installation

### Step 1 — Download and install the app

1. Download `Safari Chrome Sync.dmg` from the [latest release](https://github.com/bakkel/safari-chrome-sync/releases)
2. Double-click the `.dmg` file to open it
3. Drag **Safari Chrome Sync.app** to your **Applications** folder
4. Eject the DMG (drag it to Trash in Finder)

### Step 2 — Grant Full Disk Access to the app

Safari's files are protected by macOS. The app needs special permission to read them:

1. Open **System Settings** → **Privacy & Security** → **Full Disk Access**
2. Click **+** and navigate to **Applications → Safari Chrome Sync.app**
3. Confirm the toggle is enabled
4. Restart **Safari Chrome Sync** if it was already open

> ⚠️ Without this step the app cannot read Safari files and sync will not work.

### Step 3 — Launch the app

Open **Applications** folder and double-click **Safari Chrome Sync.app**.

The app window will open. The app also installs a LaunchAgent that starts it automatically at login.

---

## Building from source (for developers)

If you want to build the app yourself:

### Prerequisites
- Python 3.9 or higher
- PyQt6 and PyInstaller installed

### Build steps

```bash
# Clone the repository
git clone https://github.com/bakkel/safari-chrome-sync.git
cd safari-chrome-sync

# Install dependencies
pip install -r requirements.txt

# Build the .app bundle with PyInstaller
pyinstaller safari_chrome_sync.spec

# Create the .dmg installer
bash build_dmg.sh

# Result: Safari Chrome Sync.dmg ready for distribution
```

---

## First-time synchronization

The first sync replaces all Chrome bookmarks with your Safari data. To ensure Google Sync doesn't interfere, start with a clean slate in Chrome.

### Step A — Remove all bookmarks and history from Chrome

**Bookmarks:**

1. Open Chrome on your Mac
2. Go to `chrome://bookmarks`
3. Open the **Bookmarks Bar** folder → select all (`Cmd+A`) → right-click → **Delete**
4. Repeat for **Other Bookmarks** and any other folders shown
5. Wait a few seconds so Google Sync can upload the empty state to the cloud

> This ensures the Google cloud is also empty, so it cannot restore old bookmarks after the sync.

**Browsing history:**

1. In Chrome, go to `chrome://settings/clearBrowserData`
2. Click the **Advanced** tab
3. Set **Time range** to **All time**
4. Check **Browsing history** (uncheck everything else to avoid deleting passwords, etc.)
5. Click **Delete data**
6. Fully close Chrome (`Cmd+Q`)

### Step B — Reset the sync state

1. Click `↔` in the menu bar
2. Choose **Reset (new first run)**
3. Confirm with **Reset**

### Step C — Run the first sync

Make sure both **Safari and Chrome are completely closed**, then:

1. Click `↔` → **Sync now**
2. Wait for the "Sync complete" notification

Chrome's bookmarks are now fully replaced with your Safari folder structure.

### Step D — Open Chrome

1. Open Chrome — it will detect the new local bookmarks
2. Google Sync will upload them to the cloud
3. Your other devices (e.g. your Windows PC) will automatically receive the Safari bookmarks

---

## Daily use

After the first sync, everything runs automatically in the background.

| Action | Result |
|---|---|
| Add a bookmark in Safari | Appears in Chrome at the next auto-sync |
| Delete a bookmark in Safari | Removed from Chrome at the next auto-sync |
| Add a bookmark in Chrome (Mac or Windows via Google Sync) | Appears in Safari at the next auto-sync |
| Delete a bookmark in Chrome | Removed from Safari at the next auto-sync |

### Application window controls

| Control | Description |
|---|---|
| **Sync Now** button | Triggers an immediate sync |
| **Auto-sync interval** | Dropdown to set automatic sync interval (5 min – 2 hrs) |
| **Sync bookmarks** checkbox | Enable / disable bookmark sync |
| **Sync history** checkbox | Enable / disable history sync |
| **Copy Log** button | Copy the entire activity log to clipboard for sharing / debugging |
| **Log viewer** | Live display of the last 50 lines of sync activity, auto-scrolling |

### Tools menu

| Option | Description |
|---|---|
| **Open Config** | View the configuration file with current sync settings |
| **Open Backups** | Access automatic backups of bookmark files created before each sync |
| **Debug: Dump Safari Structure** | Export Safari bookmark structure for inspection and troubleshooting |
| **Reset Sync State** | Clear the sync state — the next sync will treat as a fresh first run |

### Tips for reliable syncing

- Close **Chrome** before syncing if you want changes from Chrome to reach Safari.
- Close **Safari** before syncing if you want changes from Safari to reach Chrome.
- For the most reliable sync: close **both** browsers before clicking **Sync now**.

### Syncing Chrome (Windows) changes to Safari

If you have added bookmarks or visited pages in Chrome on another device (e.g. a Windows PC), those changes arrive on your Mac via Google Sync — but only after Chrome on Mac has synced them to its local files.

**Recommended workflow:**

1. Make sure Chrome on your Mac has had a moment to sync with Google (open it briefly if needed, then close it — `Cmd+Q`)
2. **Before opening Safari**, click `↔` → **Sync now**
3. The script reads the updated Chrome files and writes the changes to Safari
4. Now open Safari — it will have the latest bookmarks and history from your Windows PC

> If you open Safari first, the sync in the Chrome→Safari direction will be skipped until you close Safari again.

---

## Troubleshooting

**Sync does nothing / permission error**
→ Check that **Safari Chrome Sync.app** has Full Disk Access (see Step 2 under Installation).

**Bookmarks are not in the correct folder**
→ Run a Reset and follow the first-time sync procedure again (Steps A–D).

**Old Chrome bookmarks keep coming back**
→ Google Sync is restoring them from the cloud. Make sure to delete all Chrome bookmarks first (Step A) and wait a few seconds before running the reset, so Google Sync can upload the empty state.

**App does not appear in Applications after installation**
→ Make sure you dragged `Safari Chrome Sync.app` from the DMG to your Applications folder and waited for the copy to complete.

**App does not auto-launch at login**
→ The app installs a LaunchAgent automatically. If you move the `.app` to a different location, the LaunchAgent path may become invalid. Reinstall by launching the app again from Applications.

**View the log file directly**
```bash
tail -f ~/.safari_chrome_sync/sync.log
```

---

## Contributing

Bug reports and feature requests are welcome via [GitHub Issues](https://github.com/bakkel/safari-chrome-sync/issues).
Pull requests are appreciated — please open an issue first to discuss larger changes.

---

## License

MIT — free to use, modify and distribute.
See [LICENSE](LICENSE) for the full text.

Copyright © 2026 Michel van Helden
