import os
import stat
import sys
import json
import subprocess

from app.models import Game

EXCLUDE_TERMS = (
    "unins",
    "setup",
    "install",
    "redist",
    "readme",
    "vcredist",
    "dotnet",
    "dxsetup",
    "crash",
    "updater",
    "steam_api",
    "unitycrashhandler",
    "vc_redist",
    "config",
    "dxwebsetup",
    "dotnetfx",
    "ndp48",
    "iexplore",
    "wordpad",
    "wmplayer",
    "winedbg",
    "wineboot",
    "winecfg",
    "notepad",
    "regedit",
    "taskmgr",
    "winemine",
    "progmime",
    "mplay32",
    "write",
)

SKIP_DIR_TERMS = (
    ".git",
    "__pycache__",
    "bin",
    "node_modules",
    "redist",
    "prefix",
    "drive_c",
    "dosdevices",
    "pfx",
)

WINE_PREFIX_LOCATIONS = [
    os.path.expanduser("~/Wine Prefixes"),
    os.path.expanduser("~/Games/Wine Prefixes"),
    "/mnt/Main/Wine Prefixes",
    "/mnt/Games/Wine Prefixes",
    os.path.expanduser("~/Games"),
    os.path.expanduser("~/wineprefixes"),
    os.path.expanduser("~/.wine"),
]


def _scan_heroic_dirs():
    dirs = set()
    config_paths = [
        os.path.expanduser("~/.config/heroic/globals.json"),
    ]
    for p in config_paths:
        try:
            with open(p, "r") as f:
                data = json.load(f)
                for key in ("defaultInstallPath", "defaultInstallationPath"):
                    val = data.get(key, "")
                    if val and os.path.isdir(val):
                        dirs.add(val)
        except Exception:
            pass
    legendary_paths = [
        os.path.expanduser("~/.config/legendary/config.json"),
    ]
    for p in legendary_paths:
        try:
            with open(p, "r") as f:
                data = json.load(f)
                for key in ("install_dir", "install_directory", "installationDirectory"):
                    val = data.get(key, "")
                    if val and os.path.isdir(val):
                        dirs.add(val)
        except Exception:
            pass
    return list(dirs)


def _windows_exe_candidates(folder, depth):
    hits = []
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return hits
    for entry in entries:
        full = os.path.join(folder, entry)
        if os.path.isdir(full):
            if entry.startswith("."):
                continue
            if depth < 2 and entry.lower() not in SKIP_DIR_TERMS:
                hits.extend(_windows_exe_candidates(full, depth + 1))
            continue
        if not entry.lower().endswith(".exe"):
            continue
        if any(term in entry.lower() for term in EXCLUDE_TERMS):
            continue
        if os.path.getsize(full) < 2 * 1024 * 1024:
            continue
        base = entry[:-4]
        if any(word in base.lower() for word in ("launcher", "launch", "boot", "unins", "setup")):
            continue
        hits.append(full)
    return hits


def _linux_binary_candidates(folder, depth):
    hits = []
    try:
        entries = sorted(os.listdir(folder))
    except OSError:
        return hits
    for entry in entries:
        full = os.path.join(folder, entry)
        if os.path.isdir(full):
            if entry.startswith("."):
                continue
            if depth < 1 and entry.lower() not in SKIP_DIR_TERMS:
                hits.extend(_linux_binary_candidates(full, depth + 1))
            continue
        lower = entry.lower()
        if lower.endswith((".so", ".py", ".jar", ".dll", ".scr", ".desktop", ".service")):
            continue
        if any(term in lower for term in EXCLUDE_TERMS):
            continue
        size = os.path.getsize(full) if os.path.exists(full) else 0
        ext_ok = lower.endswith((".sh", ".AppImage", ".run", ".bin", ".x86_64"))
        if not ext_ok and not os.access(full, os.X_OK):
            continue
        if lower.endswith(".sh") and size > 0:
            hits.append(full)
            continue
        if size < 1024 * 1024:
            continue
        hits.append(full)
    return hits


def _wine_exe_name(path):
    base = os.path.basename(path)
    name = base.rsplit(".", 1)[0]
    name = name.replace("_", " ").replace("-", " ")
    for skip in ("launcher", "unins", "setup", "install", "crash", "update", "vcredist"):
        if skip in name.lower():
            return None
    return name.strip()


def detect(folders):
    games = []
    seen = set()
    scan_dirs = list(folders or [])
    scan_dirs.extend(_scan_heroic_dirs())
    for loc in WINE_PREFIX_LOCATIONS:
        if os.path.isdir(loc) and loc not in scan_dirs:
            scan_dirs.append(loc)
    for folder in scan_dirs:
        if not os.path.isdir(folder):
            continue
        candidates = _linux_binary_candidates(folder, 0)
        if "wine" in folder.lower() or "prefix" in folder.lower() or "heroic" in folder.lower():
            candidates.extend(_windows_exe_candidates(folder, 0))
        for exe in candidates:
            real = os.path.realpath(exe)
            if real in seen:
                continue
            seen.add(real)
            name = os.path.splitext(os.path.basename(exe))[0]
            name = name.split("-")[0].strip() or name
            games.append(
                Game(
                    name=name,
                    source="local",
                    launch_target=exe,
                    exe=exe,
                    install_dir=os.path.dirname(exe),
                    platform="windows" if exe.lower().endswith(".exe") else "linux",
                    manual=True,
                )
            )
    return games


def pick_manual_file(path):
    if not os.path.exists(path):
        return None
    if os.path.isdir(path):
        if sys.platform == "win32":
            cands = _windows_exe_candidates(path, 0)
        else:
            cands = _linux_binary_candidates(path, 0)
        if not cands:
            return None
        exe = cands[0]
        name = os.path.splitext(os.path.basename(exe))[0]
        return Game(
            name=name.split("-")[0].strip() or os.path.basename(path),
            source="local",
            launch_target=exe,
            exe=exe,
            install_dir=os.path.dirname(exe),
            platform="windows" if sys.platform == "win32" else "linux",
            manual=True,
        )
    exe = path
    return Game(
        name=os.path.splitext(os.path.basename(exe))[0],
        source="local",
        launch_target=exe,
        exe=exe,
        install_dir=os.path.dirname(exe),
        platform="windows" if sys.platform == "win32" else "linux",
        manual=True,
    )
