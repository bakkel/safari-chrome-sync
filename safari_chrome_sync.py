#!/usr/bin/env python3
"""
Safari ↔ Chrome Bookmark & History Synchronizer — macOS

Gebruik:
  python3 safari_chrome_sync.py sync           # Sync eenmalig uitvoeren
  python3 safari_chrome_sync.py status         # Toon sync-status
  python3 safari_chrome_sync.py config         # Toon configuratie
  python3 safari_chrome_sync.py config --interval 15  # Zet interval op 15 min
  python3 safari_chrome_sync.py config --no-history   # Schakel history sync uit
  python3 safari_chrome_sync.py reset          # Reset staat (volgende = eerste run)
  python3 safari_chrome_sync.py daemon         # Loop als daemon (gebruikt interval uit config)

Eerste run:
  - Alle Chrome-bladwijzers worden OVERSCHREVEN met Safari-structuur
  - Alle Chrome-geschiedenis wordt OVERSCHREVEN met Safari-geschiedenis

Volgende runs (tweezijdig):
  - Nieuwe bladwijzers uit Safari → Chrome (in 'Other bookmarks')
  - Nieuwe bladwijzers uit Chrome → Safari (in Bookmarks Bar)
  - Nieuwe bezoeken uit Safari → Chrome
  - Nieuwe bezoeken uit Chrome → Safari

Vereisten:
  - macOS met Safari en Google Chrome
  - Python 3.9+
  - Volledige Schijftoegang voor Terminal/Python (Systeeminstellingen → Privacy → Volledige schijftoegang)
"""

import argparse
import hashlib
import json
import logging
import os
import plistlib
import shutil
import sqlite3
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

# ── Paden ────────────────────────────────────────────────────────────────────
SYNC_DIR         = Path.home() / ".safari_chrome_sync"
CONFIG_FILE      = SYNC_DIR / "config.json"
STATE_FILE       = SYNC_DIR / "state.json"
LOG_FILE         = SYNC_DIR / "sync.log"
BACKUP_DIR       = SYNC_DIR / "backups"

SAFARI_BOOKMARKS = Path.home() / "Library/Safari/Bookmarks.plist"
SAFARI_HISTORY   = Path.home() / "Library/Safari/History.db"
CHROME_DIR       = Path.home() / "Library/Application Support/Google/Chrome/Default"
CHROME_BOOKMARKS = CHROME_DIR / "Bookmarks"
CHROME_HISTORY   = CHROME_DIR / "History"

# Chrome slaat tijd op als microseconden sinds 1601-01-01 UTC
# Unix gebruikt seconden sinds 1970-01-01 UTC; offset = 11644473600 seconden
CHROME_EPOCH_US = 11_644_473_600_000_000

# Safari (WebKit/CoreData) slaat tijd op als seconden sinds 2001-01-01 UTC (Mac absolute time)
# Unix epoch ligt 978307200 seconden vóór de Mac epoch
MAC_EPOCH_OFFSET = 978_307_200

DEFAULT_CONFIG = {
    "interval_minutes": 30,
    "sync_bookmarks": True,
    "sync_history": True,
}


# ── Logging ──────────────────────────────────────────────────────────────────
def setup_logging(verbose: bool = False):
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler(sys.stdout),
        ],
    )


log = logging.getLogger(__name__)


# ── Config & State ───────────────────────────────────────────────────────────
def load_config() -> dict:
    if CONFIG_FILE.exists():
        return {**DEFAULT_CONFIG, **json.loads(CONFIG_FILE.read_text())}
    return DEFAULT_CONFIG.copy()


def save_config(cfg: dict):
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2))


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {
        "first_run_done": False,
        "last_sync": None,
        "safari_bookmark_urls": [],
        "chrome_bookmark_urls": [],
        "last_safari_history_unix": 0.0,
        "last_chrome_history_unix": 0.0,
    }


def save_state(state: dict):
    SYNC_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


# ── Hulpfuncties ─────────────────────────────────────────────────────────────
def is_running(app: str) -> bool:
    return subprocess.run(["pgrep", "-x", app], capture_output=True).returncode == 0


def unix_to_chrome(ts: float) -> int:
    """Converteer Unix-timestamp (seconden) naar Chrome-microseconden."""
    return int(ts * 1_000_000) + CHROME_EPOCH_US


def chrome_to_unix(ts: int) -> float:
    """Converteer Chrome-microseconden naar Unix-timestamp (seconden)."""
    return (ts - CHROME_EPOCH_US) / 1_000_000


def mac_to_unix(ts: float) -> float:
    """Converteer Mac absolute time (seconden sinds 2001) naar Unix-timestamp."""
    return ts + MAC_EPOCH_OFFSET


def unix_to_mac(ts: float) -> float:
    """Converteer Unix-timestamp naar Mac absolute time (seconden sinds 2001)."""
    return ts - MAC_EPOCH_OFFSET


def backup(path: Path):
    """Maak een tijdgestempelde backup van een bestand."""
    if path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = BACKUP_DIR / f"{path.name}.{stamp}"
        shutil.copy2(path, dst)
        log.debug(f"Backup: {path.name} → {dst.name}")


def check_paths():
    """Controleer of vereiste bestanden bestaan."""
    errors = []
    if not SAFARI_BOOKMARKS.exists():
        errors.append(f"Safari-bladwijzers niet gevonden: {SAFARI_BOOKMARKS}")
    if not SAFARI_HISTORY.exists():
        errors.append(f"Safari-geschiedenis niet gevonden: {SAFARI_HISTORY}")
    if not CHROME_DIR.exists():
        errors.append(f"Chrome-profiel niet gevonden: {CHROME_DIR}")
    return errors


# ── Safari bladwijzers lezen ─────────────────────────────────────────────────
def read_safari_plist() -> dict:
    return plistlib.loads(SAFARI_BOOKMARKS.read_bytes())


def write_safari_plist(plist: dict):
    backup(SAFARI_BOOKMARKS)
    SAFARI_BOOKMARKS.write_bytes(plistlib.dumps(plist, fmt=plistlib.FMT_BINARY))


def _flatten_plist_node(node: dict, path: str) -> list:
    """Recursief Safari plist-node platslaan naar lijst van {url, title, path}."""
    t = node.get("WebBookmarkType", "")
    if t == "WebBookmarkTypeLeaf":
        url = node.get("URLString", "")
        title = node.get("URIDictionary", {}).get("title", "") or url
        if url and not url.startswith("readinglist://"):
            return [{"url": url, "title": title, "path": path}]
        return []
    if t == "WebBookmarkTypeList":
        folder = node.get("Title", "")
        if folder == "com.apple.ReadingList":
            return []
        new_path = (f"{path}/{folder}").strip("/") if folder else path
        result = []
        for child in node.get("Children", []):
            result.extend(_flatten_plist_node(child, new_path))
        return result
    return []


def flatten_safari(plist: dict) -> list:
    return _flatten_plist_node(plist, "")


def _plist_node_to_chrome(node: dict, ctr: list) -> dict | None:
    """Converteer één Safari plist-node naar Chrome JSON-formaat."""
    now = str(unix_to_chrome(time.time()))
    t = node.get("WebBookmarkType", "")

    if t == "WebBookmarkTypeLeaf":
        url = node.get("URLString", "")
        title = node.get("URIDictionary", {}).get("title", "") or url
        if not url or url.startswith("readinglist://"):
            return None
        nid = str(ctr[0]); ctr[0] += 1
        return {
            "date_added": now, "date_last_used": "0",
            "guid": str(uuid.uuid4()), "id": nid,
            "name": title, "type": "url", "url": url,
        }

    if t == "WebBookmarkTypeList":
        name = node.get("Title", "Map")
        if name == "com.apple.ReadingList":
            return None
        children = []
        for child in node.get("Children", []):
            c = _plist_node_to_chrome(child, ctr)
            if c:
                children.append(c)
        nid = str(ctr[0]); ctr[0] += 1
        return {
            "children": children, "date_added": now, "date_modified": now,
            "guid": str(uuid.uuid4()), "id": nid, "name": name, "type": "folder",
        }
    return None


def safari_plist_to_chrome_json(plist: dict) -> dict:
    """Converteer volledige Safari plist-structuur naar Chrome JSON-formaat.

    - BookmarksBar       → Chrome Bookmarks bar (volledige mapstructuur)
    - BookmarksMenu      → Chrome Other bookmarks (kinderen direct)
    - Overige secties    → Chrome Other bookmarks als map met naam sectie
      (bijv. iCloud-gesynchroniseerde mappen van andere apparaten)
    """
    ctr = [4]  # Chrome reserveert id's 1–3 voor de roots
    now = str(unix_to_chrome(time.time()))
    bar, other = [], []

    # Secties die we nooit meenemen
    SKIP_TITLES = {"com.apple.ReadingList", ""}
    SKIP_TYPES  = {"WebBookmarkTypeProxy"}

    for section in plist.get("Children", []):
        btype = section.get("WebBookmarkType", "")
        title = section.get("Title", "")

        if btype in SKIP_TYPES or title in SKIP_TITLES:
            continue

        if title == "BookmarksBar":
            # Structuur 1-op-1 naar bookmark_bar
            for child in section.get("Children", []):
                node = _plist_node_to_chrome(child, ctr)
                if node:
                    bar.append(node)

        elif title == "BookmarksMenu":
            # Kinderen direct in other
            for child in section.get("Children", []):
                node = _plist_node_to_chrome(child, ctr)
                if node:
                    other.append(node)

        else:
            # Andere secties (bijv. van andere iCloud-apparaten) als map in other
            children = []
            for child in section.get("Children", []):
                node = _plist_node_to_chrome(child, ctr)
                if node:
                    children.append(node)
            if children:
                nid = str(ctr[0]); ctr[0] += 1
                other.append({
                    "children": children, "date_added": now, "date_modified": now,
                    "guid": str(uuid.uuid4()), "id": nid,
                    "name": title, "type": "folder",
                })

    def make_root(name, nid, guid, children):
        return {
            "children": children, "date_added": now, "date_modified": now,
            "guid": guid, "id": nid, "name": name, "type": "folder",
        }

    return {
        "checksum": "",
        "roots": {
            "bookmark_bar": make_root("Bookmarks bar", "1",
                                      "00000000-0000-4000-a000-000000000001", bar),
            "other": make_root("Other bookmarks", "2",
                               "00000000-0000-4000-a000-000000000002", other),
            "synced": make_root("Mobile bookmarks", "3",
                                "00000000-0000-4000-a000-000000000003", []),
        },
        "version": 1,
    }


def _safari_folder_for_path(plist: dict, parts: list) -> dict | None:
    """Zoek of maak een Safari-map op het opgegeven pad. Geeft de map terug."""
    if not parts:
        return None
    section_title = parts[0]
    remaining = parts[1:]

    section = next(
        (c for c in plist.get("Children", []) if c.get("Title") == section_title),
        None
    )
    if section is None:
        return None

    current = section
    for part in remaining:
        found = next(
            (c for c in current.get("Children", [])
             if c.get("WebBookmarkType") == "WebBookmarkTypeList"
             and c.get("Title") == part),
            None
        )
        if found is None:
            new_folder = {
                "WebBookmarkType": "WebBookmarkTypeList",
                "Title": part,
                "Children": [],
                "WebBookmarkUUID": str(uuid.uuid4()).upper(),
            }
            current.setdefault("Children", []).append(new_folder)
            current = new_folder
        else:
            current = found
    return current


def _chrome_folder_for_path(data: dict, parts: list) -> dict:
    """Zoek of maak een Chrome-map op het opgegeven pad. Geeft de map terug."""
    now = str(unix_to_chrome(time.time()))
    roots = data["roots"]

    # Bepaal de juiste root
    if not parts or parts[0] in ("Bookmarks bar", "BookmarksBar"):
        current = roots["bookmark_bar"]
        parts = parts[1:]
    elif parts[0] in ("Other bookmarks", "BookmarksMenu"):
        current = roots["other"]
        parts = parts[1:]
    else:
        # Onbekende root → "Other bookmarks" met sectiemap
        current = roots["other"]
        # Laat parts intact zodat de sectienaam als map wordt aangemaakt

    for part in parts:
        found = next(
            (c for c in current.get("children", [])
             if c.get("type") == "folder" and c.get("name") == part),
            None
        )
        if found is None:
            nid = str(_max_id(data) + 1)
            new_folder = {
                "children": [], "date_added": now, "date_modified": now,
                "guid": str(uuid.uuid4()), "id": nid,
                "name": part, "type": "folder",
            }
            current.setdefault("children", []).append(new_folder)
            current = new_folder
        else:
            current = found
    return current


def add_safari_bookmarks_to_chrome(data: dict, bookmarks: list) -> tuple:
    """Voeg Safari-bladwijzers toe aan Chrome met behoud van mappad."""
    existing_urls = {b["url"] for b in flatten_chrome(data)}
    added = 0
    now = str(unix_to_chrome(time.time()))

    for bm in bookmarks:
        if bm["url"] in existing_urls:
            continue
        path_parts = [p for p in bm.get("path", "").split("/") if p]
        folder = _chrome_folder_for_path(data, path_parts)
        nid = str(_max_id(data) + 1)
        folder.setdefault("children", []).append({
            "date_added": now, "date_last_used": "0",
            "guid": str(uuid.uuid4()), "id": nid,
            "name": bm["title"], "type": "url", "url": bm["url"],
        })
        existing_urls.add(bm["url"])
        added += 1
    return data, added


def add_chrome_bookmarks_to_safari(plist: dict, bookmarks: list) -> tuple:
    """Voeg Chrome-bladwijzers toe aan Safari met behoud van mappad."""
    existing_urls = {b["url"] for b in flatten_safari(plist)}
    added = 0

    for bm in bookmarks:
        if bm["url"] in existing_urls:
            continue
        path_parts = [p for p in bm.get("path", "").split("/") if p]

        # Vertaal Chrome-root naar Safari-sectienaam
        if path_parts and path_parts[0] == "Bookmarks bar":
            path_parts[0] = "BookmarksBar"
        elif path_parts and path_parts[0] == "Other bookmarks":
            path_parts[0] = "BookmarksMenu"
        elif not path_parts:
            path_parts = ["BookmarksBar"]

        folder = _safari_folder_for_path(plist, path_parts)
        if folder is None:
            # Fallback: BookmarksBar root
            folder = next(
                (c for c in plist.get("Children", []) if c.get("Title") == "BookmarksBar"),
                None
            )
        if folder is None:
            continue

        folder.setdefault("Children", []).append({
            "WebBookmarkType": "WebBookmarkTypeLeaf",
            "URLString": bm["url"],
            "URIDictionary": {"title": bm["title"]},
            "WebBookmarkUUID": str(uuid.uuid4()).upper(),
        })
        existing_urls.add(bm["url"])
        added += 1
    return plist, added


# ── Chrome bladwijzers lezen/schrijven ───────────────────────────────────────
def read_chrome_bookmarks() -> dict:
    if not CHROME_BOOKMARKS.exists():
        raise FileNotFoundError(f"Chrome-bladwijzers niet gevonden: {CHROME_BOOKMARKS}")
    return json.loads(CHROME_BOOKMARKS.read_text(encoding="utf-8"))


def _compute_checksum(roots: dict) -> str:
    """Bereken Chrome-bladwijzer-checksum (MD5 over id+url/naam paren)."""
    h = hashlib.md5()

    def walk(n):
        if n.get("type") == "url":
            h.update(n.get("id", "").encode())
            h.update(n.get("url", "").encode())
        elif n.get("type") == "folder":
            h.update(n.get("id", "").encode())
            h.update(n.get("name", "").encode())
            for c in n.get("children", []):
                walk(c)

    for k in ("bookmark_bar", "other", "synced"):
        if k in roots:
            walk(roots[k])
    return h.hexdigest()


def write_chrome_bookmarks(data: dict):
    backup(CHROME_BOOKMARKS)
    data["checksum"] = _compute_checksum(data["roots"])
    CHROME_BOOKMARKS.parent.mkdir(parents=True, exist_ok=True)
    CHROME_BOOKMARKS.write_text(
        json.dumps(data, ensure_ascii=False, indent=3), encoding="utf-8"
    )
    # Verwijder Chrome's eigen backup zodat onze versie niet wordt overschreven
    bak = CHROME_BOOKMARKS.with_name("Bookmarks.bak")
    if bak.exists():
        bak.unlink()


def _flatten_chrome_node(node: dict, path: str) -> list:
    t = node.get("type", "")
    if t == "url":
        url = node.get("url", "")
        return [{"url": url, "title": node.get("name", url), "path": path}] if url else []
    if t == "folder":
        name = node.get("name", "")
        p = (f"{path}/{name}").strip("/")
        result = []
        for child in node.get("children", []):
            result.extend(_flatten_chrome_node(child, p))
        return result
    return []


def flatten_chrome(data: dict) -> list:
    result = []
    for k in ("bookmark_bar", "other", "synced"):
        if k in data.get("roots", {}):
            result.extend(_flatten_chrome_node(data["roots"][k], ""))
    return result


def _max_id(data: dict) -> int:
    m = [3]

    def walk(n):
        try:
            m[0] = max(m[0], int(n.get("id", 0)))
        except (ValueError, TypeError):
            pass
        for c in n.get("children", []):
            walk(c)

    for k in ("bookmark_bar", "other", "synced"):
        if k in data.get("roots", {}):
            walk(data["roots"][k])
    return m[0]


def remove_from_chrome(data: dict, urls: set) -> tuple:
    """Verwijder bladwijzers met de opgegeven URLs uit Chrome (recursief)."""
    removed = [0]

    def clean(node: dict) -> bool:
        if node.get("type") == "url":
            if node.get("url") in urls:
                removed[0] += 1
                return False
            return True
        if node.get("type") == "folder":
            node["children"] = [c for c in node.get("children", []) if clean(c)]
            return True
        return True

    for k in ("bookmark_bar", "other", "synced"):
        if k in data.get("roots", {}):
            clean(data["roots"][k])
    return data, removed[0]


def remove_from_safari_plist(plist: dict, urls: set) -> tuple:
    """Verwijder bladwijzers met de opgegeven URLs uit Safari plist (recursief)."""
    removed = [0]

    def clean(node: dict) -> bool:
        t = node.get("WebBookmarkType", "")
        if t == "WebBookmarkTypeLeaf":
            if node.get("URLString") in urls:
                removed[0] += 1
                return False
            return True
        if t == "WebBookmarkTypeList":
            node["Children"] = [c for c in node.get("Children", []) if clean(c)]
            return True
        return True

    for section in plist.get("Children", []):
        clean(section)
    return plist, removed[0]


def add_to_chrome(data: dict, bookmarks: list) -> tuple:
    """Voeg bladwijzers toe aan Chrome 'Other bookmarks', sla duplicaten over."""
    existing = {b["url"] for b in flatten_chrome(data)}
    nid = _max_id(data) + 1
    now = str(unix_to_chrome(time.time()))
    other = data["roots"]["other"]
    added = 0
    for bm in bookmarks:
        if bm["url"] not in existing:
            other.setdefault("children", []).append({
                "date_added": now, "date_last_used": "0",
                "guid": str(uuid.uuid4()), "id": str(nid),
                "name": bm["title"], "type": "url", "url": bm["url"],
            })
            existing.add(bm["url"])
            nid += 1
            added += 1
    other["date_modified"] = now
    return data, added


# ── Bladwijzer-synchronisatie ─────────────────────────────────────────────────
def sync_bookmarks(state: dict) -> dict:
    cfg = load_config()
    if not cfg.get("sync_bookmarks"):
        log.info("Bladwijzer-sync uitgeschakeld in configuratie")
        return state

    safari_running = is_running("Safari")
    chrome_running = is_running("Google Chrome")

    if safari_running:
        log.warning("Safari draait — Chrome→Safari sync wordt overgeslagen. Sluit Safari voor volledige tweezijdige sync.")
    if chrome_running:
        log.warning("Chrome draait — herstart Chrome na sync om bladwijzerwijzigingen te laden.")

    plist = read_safari_plist()
    safari_flat = flatten_safari(plist)
    safari_urls = {b["url"] for b in safari_flat}

    if not state.get("first_run_done"):
        # ── Eerste run: Chrome MOET gesloten zijn ─────────────────────────
        if chrome_running:
            log.error(
                "Eerste run geannuleerd: Chrome is open. "
                "Sluit Chrome volledig af en start de sync opnieuw. "
                "Chrome houdt bladwijzers in geheugen en zou onze wijzigingen overschrijven."
            )
            return state

        # ── Eerste run: Chrome volledig overschrijven met Safari-structuur ─
        log.info("Eerste run: Safari-mapstructuur 1-op-1 naar Chrome kopiëren")
        chrome_data = safari_plist_to_chrome_json(plist)
        n_bar   = len(chrome_data["roots"]["bookmark_bar"]["children"])
        n_other = len(chrome_data["roots"]["other"]["children"])
        write_chrome_bookmarks(chrome_data)
        chrome_flat = flatten_chrome(chrome_data)
        log.info(f"  Bookmarks bar: {n_bar} items  |  Other: {n_other} items  |  Totaal: {len(chrome_flat)} bladwijzers")
        state["safari_bookmark_urls"] = list(safari_urls)
        state["chrome_bookmark_urls"] = [b["url"] for b in chrome_flat]
        # Markeer dat de eerstvolgende incrementele sync Google Sync-herstel opruimt
        state["post_first_run_cleanup"] = True
        return state
    else:
        # ── Volgende runs: tweezijdige incrementele sync ──────────────────
        prev_safari = set(state.get("safari_bookmark_urls", []))
        prev_chrome = set(state.get("chrome_bookmark_urls", []))

        chrome_data = read_chrome_bookmarks()
        chrome_flat = flatten_chrome(chrome_data)
        chrome_urls = {b["url"] for b in chrome_flat}

        # ── Post-eerste-run opschoning ────────────────────────────────────
        # Na de eerste run kan Google Sync oude bladwijzers terugzetten.
        # Verwijder alles uit Chrome dat niet bij de eerste-run-schrijfactie
        # hoorde (= niet in safari_bookmark_urls staat).
        # VEREISTE: Chrome moet gesloten zijn, anders overschrijft Chrome
        # het bestand zodra het sluit of synchroniseert met Google.
        if state.get("post_first_run_cleanup"):
            if chrome_running:
                log.warning(
                    "Post-eerste-run opschoning uitgesteld: Chrome is open. "
                    "Sluit Chrome volledig af en voer de sync opnieuw uit."
                )
                # Laat de vlag staan zodat volgende sync het opnieuw probeert
                return state
            first_run_urls = set(state.get("safari_bookmark_urls", []))
            extra = chrome_urls - first_run_urls
            if extra:
                log.info(
                    f"Post-eerste-run opschoning: {len(extra)} door Google Sync "
                    f"herstelde bladwijzer(s) verwijderen uit Chrome"
                )
                chrome_data, _ = remove_from_chrome(chrome_data, extra)
                chrome_urls = {b["url"] for b in flatten_chrome(chrome_data)}
                write_chrome_bookmarks(chrome_data)
            else:
                log.info("Post-eerste-run opschoning: geen extra bladwijzers gevonden")
            state["post_first_run_cleanup"] = False
            state["chrome_bookmark_urls"] = list(chrome_urls)

        # Wijzigingen bepalen
        new_in_safari  = safari_urls - prev_safari - chrome_urls
        new_in_chrome  = chrome_urls - prev_chrome - safari_urls
        del_in_safari  = (prev_safari - safari_urls) & chrome_urls  # weg uit Safari, nog in Chrome
        del_in_chrome  = (prev_chrome - chrome_urls) & safari_urls  # weg uit Chrome, nog in Safari

        chrome_changed = False
        safari_changed = False

        # ── Safari → Chrome: toevoegingen ────────────────────────────────
        if new_in_safari:
            log.info(f"Safari→Chrome: {len(new_in_safari)} bladwijzer(s) toevoegen")
            to_add = [b for b in safari_flat if b["url"] in new_in_safari]
            chrome_data, _ = add_safari_bookmarks_to_chrome(chrome_data, to_add)
            chrome_urls = {b["url"] for b in flatten_chrome(chrome_data)}
            chrome_changed = True

        # ── Safari → Chrome: verwijderingen ──────────────────────────────
        if del_in_safari:
            log.info(f"Safari→Chrome: {len(del_in_safari)} bladwijzer(s) verwijderen")
            chrome_data, _ = remove_from_chrome(chrome_data, del_in_safari)
            chrome_urls = {b["url"] for b in flatten_chrome(chrome_data)}
            chrome_changed = True

        if chrome_changed:
            write_chrome_bookmarks(chrome_data)

        # ── Chrome → Safari: toevoegingen & verwijderingen ───────────────
        if safari_running:
            if new_in_chrome or del_in_chrome:
                log.warning(
                    f"Chrome→Safari overgeslagen "
                    f"({len(new_in_chrome)} toe te voegen, {len(del_in_chrome)} te verwijderen) "
                    f"— sluit Safari en sync opnieuw"
                )
                # Bewaar de HUIDIGE prev_chrome zodat de wijzigingen NIET als verwerkt
                # worden gemarkeerd. Op de volgende sync (Safari dicht) worden ze opnieuw
                # gedetecteerd als new_in_chrome / del_in_chrome.
                effective_chrome_urls = (chrome_urls - new_in_chrome) | del_in_chrome
            else:
                effective_chrome_urls = chrome_urls
        else:
            if new_in_chrome:
                log.info(f"Chrome→Safari: {len(new_in_chrome)} bladwijzer(s) toevoegen")
                to_add = [b for b in chrome_flat if b["url"] in new_in_chrome]
                plist, _ = add_chrome_bookmarks_to_safari(plist, to_add)
                safari_urls = {b["url"] for b in flatten_safari(plist)}
                safari_changed = True

            if del_in_chrome:
                log.info(f"Chrome→Safari: {len(del_in_chrome)} bladwijzer(s) verwijderen")
                plist, _ = remove_from_safari_plist(plist, del_in_chrome)
                safari_urls = {b["url"] for b in flatten_safari(plist)}
                safari_changed = True

            if safari_changed:
                write_safari_plist(plist)

            effective_chrome_urls = chrome_urls

        if not chrome_changed and not safari_changed:
            if not safari_running or (not new_in_chrome and not del_in_chrome):
                log.info("Bladwijzers: up-to-date, niets te synchroniseren")

        state["safari_bookmark_urls"] = list(safari_urls)
        state["chrome_bookmark_urls"] = list(effective_chrome_urls)

    return state


# ── Safari geschiedenis helpers ──────────────────────────────────────────────
def read_safari_history(since_unix: float = 0.0) -> list:
    """Lees Safari-bezoeken na `since_unix` (Unix-timestamp).

    Safari slaat visit_time op als Mac absolute time (seconden sinds 2001-01-01).
    We converteren intern naar Unix-timestamps zodat de rest van de code consistent is.
    """
    since_mac = unix_to_mac(since_unix)   # Unix → Mac absolute time voor SQL-filter
    tmp = SYNC_DIR / "_safari_hist_tmp.db"
    shutil.copy2(SAFARI_HISTORY, tmp)
    try:
        con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        rows = con.execute(
            "SELECT hi.url, hv.title, hv.visit_time "
            "FROM history_visits hv "
            "JOIN history_items hi ON hv.history_item = hi.id "
            "WHERE hv.visit_time > ? AND hv.load_successful = 1 "
            "ORDER BY hv.visit_time",
            (since_mac,)
        ).fetchall()
        con.close()
        return [
            {
                "url": r["url"],
                "title": r["title"] or "",
                "visit_time": mac_to_unix(float(r["visit_time"])),  # Mac → Unix
            }
            for r in rows
        ]
    finally:
        tmp.unlink(missing_ok=True)


def write_safari_history(visits: list):
    """Voeg bezoeken in aan Safari History.db."""
    if not visits:
        return
    backup(SAFARI_HISTORY)
    con = sqlite3.connect(SAFARI_HISTORY)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        added = 0
        for v in visits:
            url, title = v["url"], v["title"]
            vt_mac = unix_to_mac(v["visit_time"])  # Unix → Mac absolute time voor Safari DB
            con.execute(
                "INSERT OR IGNORE INTO history_items(url, visit_count) VALUES(?, 1)",
                (url,)
            )
            con.execute(
                "UPDATE history_items SET visit_count = visit_count + 1 WHERE url = ?",
                (url,)
            )
            row = con.execute(
                "SELECT id FROM history_items WHERE url = ?", (url,)
            ).fetchone()
            if row:
                exists = con.execute(
                    "SELECT 1 FROM history_visits WHERE history_item = ? AND visit_time = ?",
                    (row[0], vt_mac)
                ).fetchone()
                if not exists:
                    con.execute(
                        "INSERT INTO history_visits(history_item, visit_time, title, load_successful) "
                        "VALUES(?, ?, ?, 1)",
                        (row[0], vt_mac, title)
                    )
                    added += 1
        con.commit()
        log.info(f"  {added} bezoek(en) aan Safari-geschiedenis toegevoegd")
    finally:
        con.close()


# ── Chrome geschiedenis helpers ──────────────────────────────────────────────
def read_chrome_history(since_unix: float = 0.0) -> list:
    """Lees Chrome-bezoeken na `since_unix` (Unix-timestamp)."""
    tmp = SYNC_DIR / "_chrome_hist_tmp.db"
    shutil.copy2(CHROME_HISTORY, tmp)
    try:
        con = sqlite3.connect(f"file:{tmp}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        since_chrome = unix_to_chrome(since_unix)
        rows = con.execute(
            "SELECT u.url, u.title, v.visit_time "
            "FROM visits v "
            "JOIN urls u ON v.url = u.id "
            "WHERE v.visit_time > ? "
            "ORDER BY v.visit_time",
            (since_chrome,)
        ).fetchall()
        con.close()
        return [
            {
                "url": r["url"],
                "title": r["title"] or "",
                "visit_time": chrome_to_unix(r["visit_time"]),
            }
            for r in rows
        ]
    finally:
        tmp.unlink(missing_ok=True)


def _clear_chrome_history_tables(con: sqlite3.Connection):
    """Verwijder alle URLs en bezoeken uit Chrome's History.db."""
    con.execute("PRAGMA foreign_keys = OFF")
    con.execute("DELETE FROM visits")
    con.execute("DELETE FROM urls")
    for tbl in ("keyword_search_terms", "segments", "segment_usage"):
        try:
            con.execute(f"DELETE FROM {tbl}")
        except sqlite3.OperationalError:
            pass
    con.execute("PRAGMA foreign_keys = ON")


def write_chrome_history(visits: list):
    """Voeg bezoeken in aan Chrome History.db."""
    if not visits:
        return
    backup(CHROME_HISTORY)
    con = sqlite3.connect(CHROME_HISTORY)
    try:
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=OFF")
        added = 0
        for v in visits:
            url, title, vt_chrome = v["url"], v["title"], unix_to_chrome(v["visit_time"])
            # Gebruik SELECT+UPDATE/INSERT in plaats van ON CONFLICT
            # (Chrome's urls-tabel heeft geen expliciete UNIQUE constraint op url)
            row = con.execute("SELECT id, visit_count FROM urls WHERE url = ?", (url,)).fetchone()
            if row:
                uid, vc = row
                new_title = title if title else con.execute(
                    "SELECT title FROM urls WHERE id=?", (uid,)
                ).fetchone()[0]
                con.execute(
                    "UPDATE urls SET visit_count=?, last_visit_time=MAX(last_visit_time,?), title=? WHERE id=?",
                    (vc + 1, vt_chrome, new_title, uid)
                )
            else:
                con.execute(
                    "INSERT INTO urls(url, title, visit_count, last_visit_time, hidden) VALUES(?,?,1,?,0)",
                    (url, title, vt_chrome)
                )
            row = con.execute(
                "SELECT id FROM urls WHERE url = ?", (url,)
            ).fetchone()
            if row:
                exists = con.execute(
                    "SELECT 1 FROM visits WHERE url = ? AND visit_time = ?",
                    (row[0], vt_chrome)
                ).fetchone()
                if not exists:
                    # transition 805306368 = LINK (normaal klik)
                    con.execute(
                        "INSERT INTO visits(url, visit_time, transition) VALUES(?, ?, 805306368)",
                        (row[0], vt_chrome)
                    )
                    added += 1
        con.commit()
        log.info(f"  {added} bezoek(en) aan Chrome-geschiedenis toegevoegd")
    finally:
        con.close()


# ── Geschiedenis-synchronisatie ──────────────────────────────────────────────
def sync_history(state: dict) -> dict:
    cfg = load_config()
    if not cfg.get("sync_history"):
        log.info("Geschiedenis-sync uitgeschakeld in configuratie")
        return state

    chrome_running = is_running("Google Chrome")
    safari_running = is_running("Safari")

    if chrome_running:
        log.warning(
            "Chrome draait — geschiedenis-sync overgeslagen (database is vergrendeld). "
            "Sluit Chrome en voer sync opnieuw uit."
        )
        return state

    if not state.get("first_run_done"):
        # ── Eerste run: Chrome-geschiedenis volledig overschrijven ─────────
        log.info("Eerste run: ALLE Safari-geschiedenis naar Chrome schrijven (overschrijven)")
        all_safari = read_safari_history(since_unix=0.0)
        log.info(f"  {len(all_safari)} Safari-bezoeken gevonden")

        backup(CHROME_HISTORY)
        con = sqlite3.connect(CHROME_HISTORY)
        try:
            con.execute("PRAGMA journal_mode=WAL")
            _clear_chrome_history_tables(con)
            con.commit()
        finally:
            con.close()

        write_chrome_history(all_safari)

        last_ts = max((v["visit_time"] for v in all_safari), default=0.0)
        state["last_safari_history_unix"] = last_ts
        state["last_chrome_history_unix"] = last_ts

    else:
        # ── Volgende runs: tweezijdige incrementele sync ──────────────────
        last_safari = state.get("last_safari_history_unix", 0.0)
        last_chrome = state.get("last_chrome_history_unix", 0.0)

        new_safari = read_safari_history(since_unix=last_safari)
        new_chrome = read_chrome_history(since_unix=last_chrome)

        log.info(
            f"Nieuwe bezoeken — Safari: {len(new_safari)}, Chrome: {len(new_chrome)}"
        )

        # Safari → Chrome (sla dubbelen over via (url, afgeronde tijd))
        chrome_key = {(v["url"], round(v["visit_time"])) for v in new_chrome}
        to_chrome = [
            v for v in new_safari
            if (v["url"], round(v["visit_time"])) not in chrome_key
        ]
        write_chrome_history(to_chrome)

        # Chrome → Safari
        if not safari_running:
            safari_key = {(v["url"], round(v["visit_time"])) for v in new_safari}
            to_safari = [
                v for v in new_chrome
                if (v["url"], round(v["visit_time"])) not in safari_key
            ]
            write_safari_history(to_safari)
        else:
            log.warning("Safari draait — Chrome→Safari geschiedenis-sync overgeslagen")

        if not new_safari and not new_chrome:
            log.info("Geschiedenis: up-to-date, niets te synchroniseren")

        if new_safari:
            state["last_safari_history_unix"] = max(v["visit_time"] for v in new_safari)
        if new_chrome:
            state["last_chrome_history_unix"] = max(v["visit_time"] for v in new_chrome)

    return state


# ── Hoofd-sync ────────────────────────────────────────────────────────────────
def run_sync(verbose: bool = False):
    setup_logging(verbose)
    log.info("═══ Sync gestart ════════════════════════════════════════════")

    errors = check_paths()
    if errors:
        for e in errors:
            log.error(e)
        log.error(
            "Controleer of Safari en Chrome geïnstalleerd zijn en of dit script "
            "Volledige Schijftoegang heeft (Systeeminstellingen → Privacy → Volledige schijftoegang)"
        )
        sys.exit(1)

    state = load_state()
    cfg = load_config()
    was_first_run = not state.get("first_run_done", False)

    try:
        if cfg.get("sync_bookmarks"):
            log.info("── Bladwijzers synchroniseren ──")
            state = sync_bookmarks(state)
    except Exception as e:
        log.error(f"Bladwijzer-sync mislukt: {e}", exc_info=True)

    try:
        if cfg.get("sync_history"):
            log.info("── Geschiedenis synchroniseren ──")
            state = sync_history(state)
    except Exception as e:
        log.error(f"Geschiedenis-sync mislukt: {e}", exc_info=True)

    # Markeer eerste run als voltooid — MAAR niet als Chrome draaide en de eerste
    # run daardoor geblokkeerd was (sync_bookmarks keert dan ongewijzigd terug).
    if was_first_run and is_running("Google Chrome"):
        log.warning(
            "Eerste run NIET gemarkeerd als voltooid — Chrome was open. "
            "Sluit Chrome en voer de sync opnieuw uit."
        )
    else:
        state["first_run_done"] = True

    state["last_sync"] = datetime.now().isoformat()
    save_state(state)
    log.info("═══ Sync voltooid ═══════════════════════════════════════════")


# ── CLI ───────────────────────────────────────────────────────────────────────
def cmd_sync(args):
    run_sync(verbose=getattr(args, "verbose", False))


def cmd_status(args):
    setup_logging()
    state = load_state()
    cfg = load_config()

    last = state.get("last_sync")
    if last:
        try:
            last = datetime.fromisoformat(last).strftime("%d-%m-%Y %H:%M:%S")
        except ValueError:
            pass

    print(f"\nSafari ↔ Chrome Sync — Status")
    print(f"──────────────────────────────")
    print(f"Eerste run gedaan:        {state.get('first_run_done', False)}")
    print(f"Laatste sync:             {last or 'nooit'}")
    print(f"Safari-bladwijzers:       {len(state.get('safari_bookmark_urls', []))}")
    print(f"Chrome-bladwijzers:       {len(state.get('chrome_bookmark_urls', []))}")

    last_s = state.get("last_safari_history_unix", 0.0)
    last_c = state.get("last_chrome_history_unix", 0.0)
    fmt = lambda ts: datetime.fromtimestamp(ts).strftime("%d-%m-%Y %H:%M") if ts else "nooit"
    print(f"Safari-geschiedenis t/m:  {fmt(last_s)}")
    print(f"Chrome-geschiedenis t/m:  {fmt(last_c)}")
    print(f"\nConfiguratie")
    print(f"──────────────────────────────")
    print(f"Interval:                 {cfg.get('interval_minutes')} minuten")
    print(f"Bladwijzer-sync:          {'aan' if cfg.get('sync_bookmarks') else 'uit'}")
    print(f"Geschiedenis-sync:        {'aan' if cfg.get('sync_history') else 'uit'}")
    print(f"Config-bestand:           {CONFIG_FILE}")
    print(f"Logbestand:               {LOG_FILE}")
    print()


def cmd_config(args):
    setup_logging()
    cfg = load_config()

    if args.interval is not None:
        cfg["interval_minutes"] = args.interval
        print(f"Interval ingesteld op {args.interval} minuten")

    if args.no_bookmarks:
        cfg["sync_bookmarks"] = False
        print("Bladwijzer-sync uitgeschakeld")
    if args.enable_bookmarks:
        cfg["sync_bookmarks"] = True
        print("Bladwijzer-sync ingeschakeld")
    if args.no_history:
        cfg["sync_history"] = False
        print("Geschiedenis-sync uitgeschakeld")
    if args.enable_history:
        cfg["sync_history"] = True
        print("Geschiedenis-sync ingeschakeld")

    save_config(cfg)
    print(json.dumps(cfg, indent=2))

    plist_path = Path.home() / "Library/LaunchAgents/com.safari-chrome-sync.plist"
    if plist_path.exists() and args.interval is not None:
        print(
            f"\nLet op: voer 'bash install.sh' opnieuw uit om het nieuwe interval "
            f"door te voeren in de LaunchAgent."
        )


def cmd_reset(args):
    setup_logging()
    if STATE_FILE.exists():
        STATE_FILE.unlink()
        print("Staat gereset. De volgende sync wordt behandeld als eerste run.")
    else:
        print("Geen staat-bestand gevonden.")


def cmd_debug(args):
    """Dump Safari plist-structuur naar ~/.safari_chrome_sync/debug_safari.txt"""
    setup_logging()
    out = SYNC_DIR / "debug_safari.txt"
    SYNC_DIR.mkdir(parents=True, exist_ok=True)

    plist = read_safari_plist()
    lines = []

    def dump(node, indent=0):
        t = node.get("WebBookmarkType", "")
        prefix = "  " * indent
        if t == "WebBookmarkTypeLeaf":
            url   = node.get("URLString", "")
            title = node.get("URIDictionary", {}).get("title", "") or url
            lines.append(f"{prefix}[URL] {title[:70]}  →  {url[:80]}")
        elif t == "WebBookmarkTypeList":
            title    = node.get("Title", "(geen titel)")
            children = node.get("Children", [])
            lines.append(f"{prefix}[MAP] \"{title}\"  ({len(children)} kinderen)")
            for child in children:
                dump(child, indent + 1)
        else:
            lines.append(f"{prefix}[?] type={t}  title={node.get('Title','')}")

    dump(plist)
    text = "\n".join(lines)
    out.write_text(text, encoding="utf-8")
    print(f"Safari-structuur opgeslagen in:\n  {out}\n")
    # Druk ook de eerste 60 regels af
    for line in lines[:60]:
        print(line)
    if len(lines) > 60:
        print(f"... (+{len(lines)-60} regels, zie bestand)")


def cmd_daemon(args):
    verbose = getattr(args, "verbose", False)
    setup_logging(verbose)
    cfg = load_config()
    interval = cfg.get("interval_minutes", 30) * 60
    log.info(f"Daemon-modus: sync elke {cfg.get('interval_minutes')} minuten")
    while True:
        try:
            run_sync(verbose=verbose)
        except Exception as e:
            log.error(f"Sync-fout: {e}", exc_info=True)
        log.info(f"Volgende sync over {cfg.get('interval_minutes')} minuten...")
        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(
        description="Safari ↔ Chrome Bladwijzer & Geschiedenis Sync",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="cmd", metavar="opdracht")

    p_sync = sub.add_parser("sync", help="Sync eenmalig uitvoeren")
    p_sync.add_argument("-v", "--verbose", action="store_true", help="Uitgebreide uitvoer")

    sub.add_parser("status", help="Toon sync-status")
    sub.add_parser("reset", help="Reset staat (volgende = eerste run)")

    p_cfg = sub.add_parser("config", help="Bekijk/wijzig configuratie")
    p_cfg.add_argument("--interval", type=int, metavar="MINUTEN",
                       help="Sync-interval instellen")
    p_cfg.add_argument("--no-bookmarks", action="store_true",
                       help="Bladwijzer-sync uitschakelen")
    p_cfg.add_argument("--enable-bookmarks", action="store_true",
                       help="Bladwijzer-sync inschakelen")
    p_cfg.add_argument("--no-history", action="store_true",
                       help="Geschiedenis-sync uitschakelen")
    p_cfg.add_argument("--enable-history", action="store_true",
                       help="Geschiedenis-sync inschakelen")

    p_dmn = sub.add_parser("daemon", help="Draai als achtergrond-daemon")
    p_dmn.add_argument("-v", "--verbose", action="store_true")

    sub.add_parser("debug", help="Dump Safari plist-structuur naar debug-bestand")

    args = parser.parse_args()

    dispatch = {
        "sync":   cmd_sync,
        "status": cmd_status,
        "config": cmd_config,
        "reset":  cmd_reset,
        "daemon": cmd_daemon,
        "debug":  cmd_debug,
    }

    if args.cmd in dispatch:
        dispatch[args.cmd](args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
