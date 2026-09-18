import os
import sys

from app.models import Game
from .vdf import load_vdf

SKIP_NAMES = {
    "steamworks common redistributables",
    "steam linux runtime",
    "steam vr",
}
IGNORED_APPIDS = {"480"}
HEADER_URL = "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"


def _winreg_steam_path():
    try:
        import winreg
    except ImportError:
        return None
    for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
        try:
            with winreg.OpenKey(hive, r"Software\Valve\Steam") as key:
                val, _ = winreg.QueryValueEx(key, "SteamPath")
                if val:
                    return val
        except OSError:
            continue
    return None


def steam_roots():
    roots = []
    if sys.platform == "win32":
        p = _winreg_steam_path()
        if p:
            roots.append(p)
        roots.append(r"C:\Program Files (x86)\Steam")
    else:
        candidates = [
            os.path.expanduser("~/.steam/steam"),
            os.path.expanduser("~/.local/share/Steam"),
            os.path.join(os.environ.get("XDG_DATA_HOME", ""), "Steam"),
            os.path.expanduser("~/.var/app/com.valvesoftware.Steam/data/Steam"),
        ]
        roots = [c for c in candidates if c]
    out = []
    seen = set()
    for r in roots:
        if not r or not os.path.isdir(r):
            continue
        real = os.path.realpath(r)
        if real in seen:
            continue
        seen.add(real)
        out.append(r)
    return out


def _library_paths(root):
    paths = []
    for rel in (
        "steamapps/libraryfolders.vdf",
        "config/libraryfolders.vdf",
        "steamapps",
    ):
        f = os.path.join(root, rel)
        if os.path.isfile(f):
            data = load_vdf(f)
            if not data:
                continue
            folders = data.get("libraryfolders", {})
            if isinstance(folders, dict):
                for key, entry in folders.items():
                    if not isinstance(entry, dict):
                        continue
                    p = entry.get("path")
                    if p:
                        paths.append(p)
            if not paths:
                paths.append(root)
            out = []
            seen = set()
            for p in paths:
                if not p:
                    continue
                real = os.path.realpath(p)
                if real in seen:
                    continue
                seen.add(real)
                out.append(p)
            return out
    return [root]


def detect():
    games = []
    for root in steam_roots():
        for lib in _library_paths(root):
            steamapps = os.path.join(lib, "steamapps")
            if not os.path.isdir(steamapps):
                continue
            for fn in os.listdir(steamapps):
                if not (fn.startswith("appmanifest_") and fn.endswith(".acf")):
                    continue
                acf = load_vdf(os.path.join(steamapps, fn))
                if not acf:
                    continue
                if "AppState" in acf and isinstance(acf["AppState"], dict):
                    acf = acf["AppState"]
                appid = str(acf.get("appid", "")).strip()
                name = (acf.get("name") or "").strip()
                installdir = (acf.get("installdir") or "").strip()
                if not appid or not name:
                    continue
                lower = name.lower()
                if (
                    lower in SKIP_NAMES
                    or "proton" in lower
                    or "linux runtime" in lower
                    or appid in IGNORED_APPIDS
                ):
                    continue
                install_dir = os.path.join(steamapps, "common", installdir) if installdir else ""
                last_played = acf.get("LastPlayed")
                lp_ts = 0
                if last_played:
                    try:
                        lp_ts = int(last_played)
                    except (ValueError, TypeError):
                        pass
                games.append(
                    Game(
                        name=name,
                        source="steam",
                        launch_target=appid,
                        install_dir=install_dir,
                        cover_url=HEADER_URL.format(appid=appid),
                        platform="windows" if sys.platform == "win32" else "linux",
                        appid=appid,
                        last_played=lp_ts,
                    )
                )
    return games