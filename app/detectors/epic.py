import json
import os
import sys

from app.models import Game

SKIP_NAMES = {
    "unreal engine",
    "epic games launcher",
    "fortnite early access",
    "battle breakers",
    "rocket league",
}


def _windows_manifests():
    base = os.path.join(
        os.environ.get("ProgramData", r"C:\ProgramData"),
        "Epic",
        "EpicGamesLauncher",
        "Data",
        "Manifests",
    )
    out = []
    if not os.path.isdir(base):
        return out
    for fn in sorted(os.listdir(base)):
        if not fn.endswith(".item"):
            continue
        try:
            with open(os.path.join(base, fn), "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        name = data.get("DisplayName") or data.get("AppName") or ""
        appid = data.get("AppName") or ""
        loc = data.get("InstallLocation") or ""
        if not name or not appid:
            continue
        if any(skip in name.lower() for skip in SKIP_NAMES):
            continue
        out.append((name, appid, loc))
    return out


def _legendary_installed():
    candidates = [
        os.path.expanduser("~/.config/legendary/installed.json"),
        os.path.expanduser("~/.config/heroic/legendaryConfig/legendary/installed.json"),
    ]
    for path in candidates:
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except Exception:
            continue
        out = []
        for appid, info in data.items():
            title = info.get("title") or appid
            if any(skip in title.lower() for skip in SKIP_NAMES):
                continue
            out.append((title, appid, info.get("install_path", "")))
        return out
    return []


def detect():
    games = []
    if sys.platform == "win32":
        for name, appid, loc in _windows_manifests():
            games.append(
                Game(
                    name=name,
                    source="epic",
                    launch_target=appid,
                    install_dir=loc,
                    platform="windows",
                )
            )
    else:
        for name, appid, loc in _legendary_installed():
            games.append(
                Game(
                    name=name,
                    source="epic",
                    launch_target=appid,
                    install_dir=loc,
                    platform="linux",
                )
            )
    return games