import hashlib
import os
import re

from PIL import Image, ImageDraw, ImageFont

from app.config import CACHE_DIR

COVER_SIZE = (460, 215)
PALETTE = [
    (0x6C, 0x5C, 0xE7),
    (0xE0, 0x5B, 0x8F),
    (0x2E, 0xA1, 0x9A),
    (0xE0, 0x84, 0x3D),
    (0x3D, 0x6C, 0xC7),
    (0x8F, 0x3D, 0x3D),
    (0x5B, 0x8F, 0x3D),
    (0xB5, 0x3D, 0xC7),
]

_search_cache = {}


def cache_path(game_id):
    return os.path.join(CACHE_DIR, f"{game_id}.jpg")


def _placeholder(game):
    seed = int(hashlib.md5(game["id"].encode("utf-8")).hexdigest()[:8], 16)
    c1 = PALETTE[seed % len(PALETTE)]
    c2 = tuple(((v + 40) % 256) for v in c1)
    img = Image.new("RGB", COVER_SIZE, c1)
    d = ImageDraw.Draw(img)
    for i, y in enumerate(range(COVER_SIZE[1])):
        ratio = y / COVER_SIZE[1]
        color = tuple(int(a + (b - a) * ratio) for a, b in zip(c1, c2))
        d.line([(0, y), (COVER_SIZE[0], y)], fill=color)
    px, py = COVER_SIZE[0] // 2, int(COVER_SIZE[1] * 0.42)
    r = COVER_SIZE[0]
    d.ellipse([px - r // 5, py - r // 5, px + r // 5, py + r // 5], fill=(255, 255, 255))
    name = game.get("name") or "?"
    initials = "".join(w[0] for w in name.split()[:2])
    try:
        font_path = "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"
        if os.path.isfile(font_path):
            font = ImageFont.truetype(font_path, 64)
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()
    mbw = d.textbbox((0, 0), initials, font=font)
    tw = mbw[2] - mbw[0]
    d.text((px - tw / 2 - mbw[0], py - 30), initials, font=font, fill=(255, 255, 255))
    return img


def _fetch_image(url):
    try:
        import requests
        resp = requests.get(url, timeout=10, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        if resp.status_code == 200 and len(resp.content) > 2000:
            from io import BytesIO
            img = Image.open(BytesIO(resp.content)).convert("RGB")
            w, h = img.size
            if w >= 100 and h >= 60:
                return img
    except Exception:
        pass
    return None


def _search_steam(name):
    try:
        import requests
        from urllib.parse import quote

        clean = re.sub(r'[^\w\s]', '', name).strip()
        if not clean:
            return None

        url = f"https://store.steampowered.com/api/storesearch/?term={quote(clean)}&l=english&cc=US"
        resp = requests.get(url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
        })
        if resp.status_code != 200:
            return None

        data = resp.json()
        items = data.get("items", [])
        if not items:
            return None

        appid = items[0].get("id")
        if appid:
            return f"https://cdn.akamai.steamstatic.com/steam/apps/{appid}/header.jpg"
    except Exception:
        pass
    return None


def _search_wikipedia(name):
    try:
        import requests
        from urllib.parse import quote

        clean = re.sub(r'[^\w\s]', '', name).strip()
        if not clean:
            return None

        search_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(clean)}"
        resp = requests.get(search_url, timeout=8, headers={
            "User-Agent": "InsomniaLauncher/1.0 (contact@example.com)"
        })
        if resp.status_code == 200:
            data = resp.json()
            thumb = data.get("thumbnail", {})
            source = thumb.get("source", "")
            if source and "svg" not in source.lower():
                return source
    except Exception:
        pass

    try:
        import requests
        from urllib.parse import quote

        search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={quote(name + ' video game')}&format=json&srlimit=1"
        resp = requests.get(search_url, timeout=8, headers={
            "User-Agent": "InsomniaLauncher/1.0 (contact@example.com)"
        })
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("query", {}).get("search", [])
            if results:
                title = results[0].get("title", "")
                if title:
                    page_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote(title)}"
                    resp2 = requests.get(page_url, timeout=8, headers={
                        "User-Agent": "InsomniaLauncher/1.0 (contact@example.com)"
                    })
                    if resp2.status_code == 200:
                        data2 = resp2.json()
                        thumb = data2.get("thumbnail", {})
                        source = thumb.get("source", "")
                        if source and "svg" not in source.lower():
                            return source
    except Exception:
        pass
    return None


def _search_igdb(name):
    try:
        import requests
        from urllib.parse import quote

        clean = re.sub(r'[^\w\s]', '', name).strip()
        if not clean:
            return None

        search_url = f"https://www.igdb.com/games/{quote(clean.lower().replace(' ', '-'))}"
        resp = requests.get(search_url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "Accept": "text/html"
        })
        if resp.status_code == 200:
            html = resp.text
            og_match = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', html)
            if og_match:
                url = og_match.group(1)
                if url and url.startswith("http"):
                    return url
    except Exception:
        pass
    return None


def _search_opengameart(name):
    try:
        import requests
        from urllib.parse import quote

        clean = re.sub(r'[^\w\s]', '', name).strip()
        if not clean:
            return None

        api_url = f"https://opengameart.org/api/1/content?search={quote(clean)}&field_type_art=t&keys=title&limit=1"
        resp = requests.get(api_url, timeout=8, headers={
            "User-Agent": "Mozilla/5.0"
        })
        if resp.status_code == 200:
            data = resp.json()
            nodes = data.get("data", [])
            if nodes:
                node = nodes[0]
                uri = node.get("field_art_images", {}).get("und", [{}])
                if uri and isinstance(uri, list):
                    url = uri[0].get("url", "")
                    if url:
                        if url.startswith("/"):
                            url = "https://opengameart.org" + url
                        return url
    except Exception:
        pass
    return None


def _search_game(name):
    cache_key = name.lower().strip()
    if cache_key in _search_cache:
        return _search_cache[cache_key]

    sources = [
        ("steam", _search_steam),
        ("wikipedia", _search_wikipedia),
        ("igdb", _search_igdb),
    ]

    for source_name, search_fn in sources:
        url = search_fn(name)
        if url:
            _search_cache[cache_key] = url
            return url

    _search_cache[cache_key] = None
    return None


def fetch_one(game):
    path = cache_path(game["id"])
    if os.path.isfile(path) and os.path.getsize(path) > 0:
        return game["id"], path

    url = game.get("cover_url") or ""
    img = None

    if url:
        img = _fetch_image(url)

    if img is None:
        search_url = _search_game(game.get("name", ""))
        if search_url:
            img = _fetch_image(search_url)

    if img is None:
        img = _placeholder(game)
    else:
        img = img.resize(COVER_SIZE, Image.LANCZOS)

    try:
        img.save(path, "JPEG", quality=85)
    except OSError:
        os.makedirs(CACHE_DIR, exist_ok=True)
        img.save(path, "JPEG", quality=85)

    return game["id"], path
