import json
import os
import time

try:
    import requests
except ImportError:
    requests = None

from app.config import DATA_DIR

STEAM_API_KEY_FILE = os.path.join(DATA_DIR, "steam_api_key.txt")
STEAM_PLAYTIME_CACHE = os.path.join(DATA_DIR, "steam_playtime.json")
CACHE_TTL = 3600 * 6


def get_steam_api_key():
    if os.path.isfile(STEAM_API_KEY_FILE):
        with open(STEAM_API_KEY_FILE) as f:
            return f.read().strip()
    return ""


def set_steam_api_key(key):
    os.makedirs(os.path.dirname(STEAM_API_KEY_FILE), exist_ok=True)
    with open(STEAM_API_KEY_FILE, "w") as f:
        f.write(key.strip())


def _steam_owner_id():
    from app.detectors.steam import steam_roots, _library_paths
    from app.detectors.vdf import load_vdf
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
                owner = acf.get("LastOwner")
                if owner:
                    return str(owner).strip()
    return None


def _get_steam_id():
    owner = _steam_owner_id()
    if owner:
        return owner
    from app.detectors.steam import steam_roots
    roots = steam_roots()
    if not roots:
        return None
    loginusers = os.path.join(roots[0], "config", "loginusers.vdf")
    if not os.path.isfile(loginusers):
        return None
    from app.detectors.vdf import load_vdf
    d = load_vdf(loginusers)
    if not d or "users" not in d:
        return None
    users = d["users"]
    if not isinstance(users, dict) or not users:
        return None

    def _sort_key(item):
        data = item[1] if isinstance(item[1], dict) else {}
        auto = 0 if data.get("AutoLogin") == "1" else 1
        try:
            ts = int(data.get("Timestamp", 0) or 0)
        except (ValueError, TypeError):
            ts = 0
        return (auto, -ts)

    return max(users.items(), key=_sort_key)[0]


def query_playtime(api_key, steam_id):
    if not requests:
        return None, "requests library unavailable"
    if not api_key:
        return None, "no API key set"
    if not steam_id:
        return None, "could not determine Steam ID"
    url = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params = {
        "key": api_key,
        "steamid": steam_id,
        "include_appinfo": 1,
        "include_playtime": 1,
    }
    try:
        r = requests.get(url, params=params, timeout=15)
        if r.status_code != 200:
            try:
                body = r.json()
                msg = body.get("error") or body.get("message") or ""
            except Exception:
                msg = ""
            if not msg and r.status_code in (401, 403):
                msg = "invalid API key"
            return None, f"HTTP {r.status_code}: {msg}".strip()
        data = r.json()
        resp = data.get("response") or {}
        games = resp.get("games") or []
        out = {}
        for g in games:
            appid = str(g.get("appid", ""))
            playtime = g.get("playtime_forever", 0)
            last_played = g.get("rtime_last_played", 0)
            if not appid:
                continue
            if playtime:
                out[appid] = {"playtime": playtime * 60, "last_played": last_played}
            elif last_played:
                out[appid] = {"playtime": 0, "last_played": last_played}
        return out, f"OK ({len(games)} games, {len(out)} with playtime)"
    except requests.RequestException as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)


def fetch_steam_playtime(api_key=None):
    if not api_key:
        api_key = get_steam_api_key()
    data, _msg = query_playtime(api_key, _get_steam_id())
    if data is None:
        return {}
    _save_cache(data)
    return data


def check_steam_api_key(api_key):
    steam_id = _get_steam_id()
    data, msg = query_playtime(api_key, steam_id)
    if data is None:
        return False, msg or "API request failed"
    return True, msg


def _save_cache(data):
    os.makedirs(os.path.dirname(STEAM_PLAYTIME_CACHE), exist_ok=True)
    with open(STEAM_PLAYTIME_CACHE, "w") as f:
        json.dump({"ts": time.time(), "data": data}, f)


def load_playtime_cache():
    if not os.path.isfile(STEAM_PLAYTIME_CACHE):
        return {}
    try:
        with open(STEAM_PLAYTIME_CACHE) as f:
            cache = json.load(f)
        if time.time() - cache.get("ts", 0) > CACHE_TTL:
            return {}
        return cache.get("data", {})
    except Exception:
        return {}


def apply_playtime_to_games(games, api_playtime):
    for g in games:
        if g.source != "steam" or not g.appid:
            continue
        info = api_playtime.get(g.appid)
        if info:
            g.playtime = info.get("playtime", 0)
            if info.get("last_played"):
                g.last_played = info["last_played"]
    return games
