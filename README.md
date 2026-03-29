# safari-chrome-sync

A macOS menu bar app that automatically synchronizes bookmarks and browsing history between Safari and Google Chrome. Because Chrome uses Google Sync, your Safari bookmarks will also become available on Chrome on other devices — such as a Windows PC.

> **About this project**
> This tool was created by **Michel van Helden**, a non-developer, entirely with the help of [Claude](https://claude.ai) (Anthropic's AI assistant). No prior programming knowledge was required. If you find a bug or have a feature request, please open a [GitHub Issue](https://github.com/bakkel/safari-chrome-sync/issues) — feedback is always welcome.

---

## How it works

- **First sync**: all Chrome bookmarks and history are completely replaced by Safari data.
- **Subsequent syncs**: bidirectional — additions and deletions are kept in sync in both browsers.
- Safari's full folder structure is preserved 1-to-1 in Chrome.
- A `↔` icon in the macOS menu bar shows the current status and lets you trigger a manual sync or adjust settings.

---

## Requirements

- macOS with Safari and Google Chrome installed
- Python 3.9 or higher — check with `python3 --version`
- Full Disk Access for Python (see Step 2 below)

---

## Installation

### Step 1 — Place the files

Download or clone this repository and make sure the following files are in the same folder:

```
safari_chrome_sync.py
menubar_app.py
install_menubar.sh
```

### Step 2 — Grant Full Disk Access to Python

Safari's files are protected by macOS. Python needs special permission to read them:

1. Open **System Settings** → **Privacy & Security** → **Full Disk Access**
2. Click **+** and navigate to:
   `/Library/Frameworks/Python.framework/Versions/` → select your Python version → `Resources/Python.app`
3. Also add **Terminal** if it is not listed yet
4. Restart Terminal

> ⚠️ Without this step the script cannot read Safari files and sync will not work.

### Step 3 — Install the `rumps` library

```bash
pip3 install rumps
```

### Step 4 — Install the menu bar app

Open Terminal, navigate to the folder containing the files, and run:

```bash
bash install_menubar.sh
```

The `↔` icon will appear in your menu bar. The app starts automatically at login.

> **Terminal does not need to stay open.** After installation, the app runs as a background process managed by macOS (LaunchAgent). It operates completely independently of Terminal or iTerm — closing them has no effect on the sync. The app also restarts automatically after a reboot or login.
>
> Only if you start the app manually with `python3 menubar_app.py` (without installing) will it stop when you close Terminal.

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

After the first sync everything runs automatically in the background.

| Action | Result |
|---|---|
| Add a bookmark in Safari | Appears in Chrome at the next sync |
| Delete a bookmark in Safari | Removed from Chrome at the next sync |
| Add a bookmark in Chrome (Mac or Windows via Google Sync) | Appears in Safari at the next sync |
| Delete a bookmark in Chrome | Removed from Safari at the next sync |

### Menu bar options

| Option | Description |
|---|---|
| **Sync now** | Triggers an immediate sync |
| **Interval** | Set the automatic sync interval (5 min – 2 hrs) |
| **Sync bookmarks** | Enable / disable bookmark sync |
| **Sync history** | Enable / disable history sync |
| **Open log file** | View what was synced and when |
| **Open backup folder** | Access automatic backups of bookmark files |
| **Debug: dump Safari structure** | Export Safari bookmark structure for inspection |
| **Reset (new first run)** | Clear the sync state — triggers a full first run on next sync |
| **Quit** | Stop the menu bar app |

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
→ Check that `Python.app` has Full Disk Access (see Step 2).

**Bookmarks are not in the correct folder**
→ Run a Reset and follow the first-time sync procedure again (Steps A–D).

**Old Chrome bookmarks keep coming back**
→ Google Sync is restoring them from the cloud. Make sure to delete all Chrome bookmarks first (Step A) and wait a few seconds before running the reset, so Google Sync can upload the empty state.

**Menu bar icon has disappeared**
→ Start the app manually:
```bash
python3 /path/to/menubar_app.py &
```
Or reinstall:
```bash
bash install_menubar.sh
```

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
