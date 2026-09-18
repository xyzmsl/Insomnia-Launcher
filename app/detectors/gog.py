import os
import subprocess
import sys

from app.models import Game


def _win_registry_games():
    out = []
    try:
        import winreg
    except ImportError:
        return out
    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\GOG.com\Games"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\GOG.com\Games"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\GOG.com\Games"),
    ]
    for hive, sub in keys:
        try:
            k = winreg.OpenKey(hive, sub)
        except OSError:
            continue
        with k:
            i = 0
            while True:
                try:
                    gkey = winreg.EnumKey(k, i)
                except OSError:
                    break
                i += 1
                try:
                    with winreg.OpenKey(k, gkey) as gg:
                        name, _ = winreg.QueryValueEx(gg, "gameName")
                        path, _ = winreg.QueryValueEx(gg, "path")
                        exe, _ = winreg.QueryValueEx(gg, "exe")
                except OSError:
                    continue
                exe_path = os.path.join(path, exe) if exe else ""
                if name:
                    out.append((name, exe_path or path, path))
    return out


def _linux_dirs():
    dirs = []
    gog = os.path.expanduser("~/GOG Games")
    if os.path.isdir(gog):
        dirs.append(gog)
    mini = os.path.expanduser("~/.config/minigalaxy")
    for fn in ("config", "config.json"):
        p = os.path.join(mini, fn)
        if os.path.isfile(p):
            dirs.append(p)
    return dirs


def detect():
    games = []
    if sys.platform == "win32":
        for name, exe, install_dir in _win_registry_games():
            games.append(
                Game(
                    name=name,
                    source="gog",
                    launch_target=exe,
                    exe=exe,
                    install_dir=install_dir,
                    platform="windows",
                )
            )
    else:
        for root in _linux_dirs():
            if os.path.isfile(root):
                continue
            for entry in sorted(os.listdir(root)):
                full = os.path.join(root, entry)
                if not os.path.isdir(full):
                    continue
                candidates = []
                for fn in os.listdir(full):
                    if fn.endswith((".sh", ".AppImage")):
                        candidates.append(os.path.join(full, fn))
                if not candidates:
                    continue
                candidates.sort(key=lambda p: (os.path.splitext(p)[1] == ".sh",))
                exe = candidates[0]
                games.append(
                    Game(
                        name=entry,
                        source="gog",
                        launch_target=exe,
                        exe=exe,
                        install_dir=full,
                        platform="linux",
                    )
                )
    return games