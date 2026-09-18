import os
import shutil
import subprocess
import sys

SOURCE_LABELS = {
    "steam": "Steam",
    "epic": "Epic",
    "gog": "GOG",
    "flatpak": "Flatpak",
    "local": "Local",
}


def _launch_url(url):
    if sys.platform == "win32":
        os.startfile(url)
    else:
        subprocess.Popen(["xdg-open", url], close_fds=True)
    return None


def _launch_command(args, cwd=None):
    creationflags = 0
    if sys.platform == "win32":
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        args,
        cwd=cwd,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=(sys.platform != "win32"),
    )


def launch(game):
    source = game["source"]
    target = game["launch_target"]
    cwd = game.get("install_dir") or None
    tracked = None

    if source == "steam":
        url = f"steam://rungameid/{target}"
        tracked = _launch_url(url)
        return tracked, f"Launching via Steam: {game['name']}"

    if source == "epic":
        if game.get("exe") and os.path.isfile(game["exe"]):
            tracked = _launch_command([game["exe"]], cwd)
            return tracked, f"Launching {game['name']}"
        if sys.platform != "win32" and shutil.which("heroic"):
            tracked = _launch_command(["heroic", "--no-gui", "--launch", target])
            return tracked, f"Launching via Heroic: {game['name']}"
        url = f"com.epicgames.launcher://apps/{target}?action=launch&silent=true"
        tracked = _launch_url(url)
        return tracked, f"Launching via Epic: {game['name']}"

    if source == "flatpak":
        tracked = _launch_command(["flatpak", "run", target])
        return tracked, f"Launching {game['name']} (Flatpak)"

    if source == "gog":
        exe = game.get("exe") or target
        if exe and os.path.isfile(exe):
            tracked = _launch_command([exe], cwd)
            return tracked, f"Launching {game['name']}"
        url = f"galaxy://2.0/play/{target}" if target and not exe else ""
        if url:
            tracked = _launch_url(url)
            return tracked, f"Launching via GOG Galaxy: {game['name']}"
        return None, f"Could not find executable for {game['name']}"

    if source == "local":
        exe = game.get("exe") or target
        if not exe or not os.path.isfile(exe):
            return None, f"Executable not found: {exe}"
        if sys.platform != "win32":
            if not os.access(exe, os.X_OK):
                os.chmod(exe, 0o755)
        tracked = _launch_command([exe], cwd)
        return tracked, f"Launching {game['name']}"

    return None, f"Unknown source: {source}"