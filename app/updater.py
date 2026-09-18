import os
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

import requests

from . import config
from .version import __version__

API_URL = (
    "https://api.github.com/repos/{owner}/{repo}/releases/latest"
)


def _latest_release(owner, repo, timeout=10):
    if not owner or not repo:
        return None
    try:
        resp = requests.get(API_URL.format(owner=owner, repo=repo), timeout=timeout)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    data = resp.json()
    tag = (data.get("tag_name") or "").lstrip("v")
    return {
        "version": tag,
        "name": data.get("name") or "",
        "url": data.get("html_url") or "",
        "assets": [a for a in (data.get("assets") or []) if a.get("name")],
    }


def latest_release(timeout=10):
    return _latest_release(config.GITHUB_OWNER, config.GITHUB_REPO, timeout=timeout)


def is_newer_available(timeout=10):
    info = latest_release(timeout=timeout)
    if not info or not info["version"]:
        return None
    try:
        remote = tuple(int(x) for x in info["version"].split("."))
        local = tuple(int(x) for x in __version__.split("."))
    except ValueError:
        return None
    return info if remote > local else None


def _asset_match(asset_name):
    name = asset_name.lower()
    if sys.platform == "win32":
        return name.endswith(".exe")
    return name.endswith((".AppImage", ".bin", ".run", ".tar.gz"))


def pick_asset(info):
    if not info:
        return None
    for a in info["assets"]:
        if _asset_match(a.get("name", "")):
            return a
    return None


def download_to_temp(asset, progress=None):
    try:
        resp = requests.get(asset["browser_download_url"], stream=True, timeout=20)
    except Exception:
        return None
    if resp.status_code != 200:
        return None
    total = int(resp.headers.get("content-length") or 0)
    fd, path = tempfile.mkstemp(suffix="-" + asset["name"])
    done = 0
    with os.fdopen(fd, "wb") as fh:
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            fh.write(chunk)
            done += len(chunk)
            if progress:
                progress(done, total)
    if asset["name"].lower().endswith((".zip", ".tar.gz")):
        extracted = _extract_archive(path)
        os.remove(path)
        return extracted
    return path


def _extract_archive(archive_path):
    target = tempfile.mkdtemp(prefix="insomnia-update-")
    if archive_path.endswith(".zip"):
        with zipfile.ZipFile(archive_path) as zf:
            zf.extractall(target)
    else:
        import tarfile

        with tarfile.open(archive_path, "r:gz") as tf:
            tf.extractall(target)
    return target


def _binary_name():
    if sys.platform == "win32":
        return "InsomniaLauncher.exe"
    return "InsomniaLauncher"


def _find_binary(extracted_dir):
    name = _binary_name()
    for root, _dirs, files in os.walk(extracted_dir):
        if name in files:
            return os.path.join(root, name)
    return None


def _install_target():
    if getattr(sys, "frozen", False):
        return sys.executable
    return os.path.join(
        os.path.dirname(os.path.abspath(__file__)), _binary_name()
    )


def _stage_path(target):
    return target + ".update"


def apply_update(progress=None):
    info = is_newer_available()
    asset = pick_asset(info)
    if not asset:
        return None
    downloaded = download_to_temp(asset, progress=progress)
    if not downloaded:
        return None
    if os.path.isdir(downloaded):
        src = _find_binary(downloaded)
        if not src:
            return None
    else:
        src = downloaded
    target = _install_target()
    stage = _stage_path(target)
    try:
        os.replace(src, stage)
    except OSError:
        return None
    if not _launch_helper(stage, target):
        return None
    return target


def _relaunch_after_exit(pid, stage, target):
    code = (
        "import os, sys, time\n"
        "def main():\n"
        f"    pid, stage, target = {pid!r}, {stage!r}, {target!r}\n"
        "    while True:\n"
        "        try:\n"
        "            os.kill(pid, 0)\n"
        "        except OSError:\n"
        "            break\n"
        "        time.sleep(0.2)\n"
        "    for _ in range(50):\n"
        "        try:\n"
        "            os.replace(stage, target)\n"
        "            break\n"
        "        except OSError:\n"
        "            time.sleep(0.2)\n"
        "    if sys.platform != 'win32':\n"
        "        os.chmod(target, 0o755)\n"
        "    os.spawnv(os.P_NOWAIT, target, [target])\n"
        "def _keep_importable():\n"
        "    import concurrent.futures\n"  # keep pyinstaller modules warm (no-op)
        "if __name__ == '__main__':\n"
        "    main()\n"
    )
    fd, path = tempfile.mkstemp(suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(code)
    try:
        if sys.platform == "win32":
            subprocess.Popen(
                [sys.executable, path],
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
                close_fds=True,
            )
        else:
            subprocess.Popen(
                [sys.executable, path], start_new_session=True, close_fds=True
            )
    except OSError:
        return False
    return True


def _launch_helper(stage, target):
    return _relaunch_after_exit(os.getpid(), stage, target)
