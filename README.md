# safari-chrome-sync

A macOS menu bar app that automatically synchronizes bookmarks and browsing history between Safari and Google Chrome. Because Chrome uses Google Sync, your Safari bookmarks will also become available on Chrome on other devices — such as a Windows PC.

> **About this project**
> This tool was created by **Michel van Helden**, a non-developer, entirely with the help of [Claude](https://claude.ai) (Anthropic's AI assistant). No prior programming knowledge was required. If you find a bug or have a feature request, please open a [GitHub Issue](../../issues) — feedback is always welcome.

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

---

## First-time synchronization

The first sync requires a few extra steps because of Google Sync in Chrome. Follow them carefully — otherwise Google Sync will restore your old Chrome bookmarks after the sync.

### Step A — Temporarily disable Chrome bookmark sync

1. Open Chrome on your Mac
2. Go to `chrome://settings/syncSetup`
3. Turn off **Bookmarks** (or turn off sync entirely)
4. Fully close Chrome (`Cmd+Q`)

> This prevents Google Sync from restoring old bookmarks during the first sync.

### Step B — Reset the sync state

1. Click `↔` in the menu bar
2. Choose **Reset (new first run)**
3. Confirm with **Reset**

### Step C — Run the first sync

Make sure both **Safari and Chrome are completely closed**, then:

1. Click `↔` → **Sync now**
2. Wait for the "Sync complete" notification

Chrome's bookmarks are now fully replaced with your Safari folder structure.

### Step D — Re-enable Chrome bookmark sync

1. Open Chrome
2. Go to `chrome://settings/syncSetup`
3. Turn **Bookmarks** back on
4. Chrome will upload the Safari bookmarks to Google → they will automatically appear on your other devices (e.g. your Windows PC)

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

---

## Troubleshooting

**Sync does nothing / permission error**
→ Check that `Python.app` has Full Disk Access (see Step 2).

**Bookmarks are not in the correct folder**
→ Run a Reset and follow the first-time sync procedure again (Steps A–D).

**Old Chrome bookmarks keep coming back**
→ Google Sync is restoring them from the cloud. Make sure to temporarily disable bookmark sync in Chrome (Step A) before running the reset.

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

Bug reports and feature requests are welcome via [GitHub Issues](../../issues).
Pull requests are appreciated — please open an issue first to discuss larger changes.

---

## License

MIT — free to use, modify and distribute.
See [LICENSE](LICENSE) for the full text.

Copyright © 2026 Michel van Helden
