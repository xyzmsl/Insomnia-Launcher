import re
from app.detectors import epic, flatpak, gog, local, steam


def _fetch_genre_from_steam(name, appid=None):
    try:
        import requests
        from urllib.parse import quote

        if appid:
            url = f"https://store.steampowered.com/api/appdetails?appids={appid}&l=english"
            resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp.status_code == 200:
                data = resp.json()
                app_data = data.get(str(appid), {}).get("data", {})
                if app_data:
                    genres = app_data.get("genres", [])
                    categories = app_data.get("categories", [])
                    genre_descs = [g.get("description", "") for g in genres]
                    cat_descs = [c.get("description", "") for c in categories]
                    all_tags = genre_descs + cat_descs
                    if all_tags:
                        return ",".join(all_tags[:6])

        clean = re.sub(r'[^\w\s]', '', name).strip()
        if not clean:
            return ""

        url = f"https://store.steampowered.com/api/storesearch/?term={quote(clean)}&l=english&cc=US"
        resp = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return ""

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return ""

        found_id = items[0].get("id")
        if found_id:
            url2 = f"https://store.steampowered.com/api/appdetails?appids={found_id}&l=english"
            resp2 = requests.get(url2, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
            if resp2.status_code == 200:
                data2 = resp2.json()
                app_data = data2.get(str(found_id), {}).get("data", {})
                if app_data:
                    genres = app_data.get("genres", [])
                    categories = app_data.get("categories", [])
                    genre_descs = [g.get("description", "") for g in genres]
                    cat_descs = [c.get("description", "") for c in categories]
                    all_tags = genre_descs + cat_descs
                    if all_tags:
                        return ",".join(all_tags[:6])
    except Exception:
        pass
    return ""


def _fetch_genre_from_wiki(name):
    try:
        import requests
        from urllib.parse import quote

        clean = re.sub(r'[^\w\s]', '', name).strip()
        if not clean:
            return ""

        url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(clean)}"
        resp = requests.get(url, timeout=8, headers={
            "User-Agent": "InsomniaLauncher/1.0 (contact@example.com)"
        })
        if resp.status_code == 200:
            data = resp.json()
            desc = data.get("description", "")
            extract = data.get("extract", "")
            lower = (desc + " " + extract).lower()

            found = []
            genre_map = {
                "mmorpg": ["mmorpg", "massively multiplayer"],
                "multiplayer": ["multiplayer", "co-op", "coop", "online"],
                "singleplayer": ["single-player", "singleplayer", "single player"],
                "shooter": ["shooter", "first-person shooter", "third-person shooter"],
                "rpg": ["role-playing", "rpg", "action rpg"],
                "strategy": ["strategy", "real-time strategy", "turn-based"],
                "racing": ["racing", "racing game"],
                "puzzle": ["puzzle", "puzzle game"],
                "platformer": ["platformer", "platform game"],
                "horror": ["horror", "survival horror"],
                "fighting": ["fighting", "beat 'em up"],
                "simulation": ["simulation", "sim"],
                "open world": ["open world", "sandbox", "open-world"],
                "survival": ["survival", "survival game"],
                "action": ["action", "action-adventure"],
                "adventure": ["adventure", "point-and-click"],
            }

            for genre, keywords in genre_map.items():
                for kw in keywords:
                    if kw in lower:
                        found.append(genre)
                        break

            if found:
                return ",".join(found[:3])
    except Exception:
        pass
    return ""


GENRE_PRIORITY = {
    "mmorpg", "multiplayer", "singleplayer", "coop", "shooter", "rpg",
    "strategy", "racing", "puzzle", "platformer", "horror", "fighting",
    "simulation", "open world", "survival", "action", "adventure",
}

GENRE_SYNONYMS = {
    "massively multiplayer online role-playing": "mmorpg",
    "massively multiplayer online": "mmorpg",
    "role-playing": "rpg",
    "first-person shooter": "shooter",
    "third-person shooter": "shooter",
    "real-time strategy": "strategy",
    "turn-based strategy": "strategy",
    "racing game": "racing",
    "puzzle game": "puzzle",
    "platform game": "platformer",
    "survival horror": "horror",
    "beat 'em up": "fighting",
    "simulation game": "simulation",
    "sandbox": "open world",
    "action-adventure": "action",
    "adventure": "action",
    "single-player": "singleplayer",
    "single player": "singleplayer",
    "multi-player": "multiplayer",
    "multi player": "multiplayer",
    "co-op": "coop",
    "pvp": "multiplayer",
    "online multiplayer": "multiplayer",
    "cross-platform multiplayer": "multiplayer",
}


def _normalize_genre(raw):
    if not raw:
        return ""
    lower = raw.lower()
    for syn, canon in GENRE_SYNONYMS.items():
        lower = lower.replace(syn, canon)
    parts = [p.strip() for p in lower.split(",") if p.strip()]
    seen = set()
    result = []
    for p in parts:
        for g in GENRE_PRIORITY:
            if g in p and g not in seen:
                seen.add(g)
                result.append(g)
                break
    return ",".join(result[:3]) if result else ""


def classify_genre(name, appid=None):
    raw = _fetch_genre_from_steam(name, appid)
    if raw:
        normalized = _normalize_genre(raw)
        if normalized:
            return normalized

    raw = _fetch_genre_from_wiki(name)
    if raw:
        normalized = _normalize_genre(raw)
        if normalized:
            return normalized

    return ""


def detect_all(local_folders=None, known_genres=None):
    games = []
    for module in (steam, epic, gog, flatpak):
        try:
            games.extend(module.detect())
        except Exception:
            continue
    if local_folders:
        try:
            games.extend(local.detect(local_folders))
        except Exception:
            pass
    known_genres = known_genres or {}
    seen = set()
    out = []
    for g in games:
        gid = g.game_id()
        if gid in seen:
            continue
        seen.add(gid)
        if not g.genre:
            g.genre = known_genres.get(gid, "")
        if not g.genre:
            appid = getattr(g, 'appid', None) or g.launch_target if g.source == 'steam' else None
            g.genre = classify_genre(g.name, appid)
        out.append(g)
    return out