import os
import subprocess
import sys

from app.models import Game

DESKTOP_DIRS = [
    "/var/lib/flatpak/exports/share/applications",
    os.path.expanduser("~/.local/share/flatpak/exports/share/applications"),
]


def _desktop_categories(appid):
    for base in DESKTOP_DIRS:
        p = os.path.join(base, appid + ".desktop")
        if not os.path.isfile(p):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if line.startswith("Categories="):
                        cats = line.strip().split("=", 1)[1].lower()
                        return cats
        except OSError:
            return ""
    return ""


def _is_game(appid):
    cats = _desktop_categories(appid)
    if not cats or "game" in cats:
        return True
    return False


def detect():
    if sys.platform == "win32":
        return []
    try:
        proc = subprocess.run(
            ["flatpak", "list", "--app", "--columns=application,name"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return []
    games = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line or "\t" not in line:
            continue
        appid, _, name = line.partition("\t")
        appid = appid.strip()
        name = name.strip()
        if not appid:
            continue
        if not _is_game(appid):
            continue
        games.append(
            Game(
                name=name or appid,
                source="flatpak",
                launch_target=appid,
                platform="linux",
            )
        )
    return games