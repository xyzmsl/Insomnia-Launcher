BG = "#0d1017"
BG_SIDE = "#131820"
BG_CARD = "#1a2030"
BG_CARD_HOVER = "#222a3a"
BG_DARK = "#080b10"
ACCENT = "#6c5ce7"
ACCENT_DIM = "#5a4bd6"
ACCENT_HOVER = "#7c6cf7"
ACCENT_GREEN = "#4caf50"
ACCENT_GREEN_DIM = "#388e3c"
TEXT = "#c7d5e0"
TEXT_DIM = "#5a7090"
TEXT_HEADER = "#ffffff"
BORDER = "#1a2e50"
CARD_BORDER = "#1a2e50"
CARD_HOVER_BORDER = "#6c5ce7"
STAR_ON = "#ffc844"
STAR_OFF = "#384860"
STAT_GREEN = "#6c5ce7"
STAT_BLUE = "#4a6cd4"
STAT_ORANGE = "#e0843d"
STAT_PURPLE = "#8854d0"
INFO_BG = "#0d1017"
INFO_WIDTH = 320

CARD_IMG_SIZE = (215, 100)

SOURCE_COLORS = {
    "steam": "#4a6cd4",
    "epic": "#6c5ce7",
    "gog": "#c44422",
    "flatpak": "#9a6e30",
    "local": "#2e6b4a",
    "ea": "#e0843d",
}

GENRE_COLORS = {
    "gacha": "#e84393",
    "mmorpg": "#6c5ce7",
    "shooter": "#d63031",
    "looter shooter": "#e17055",
    "rpg": "#4a6cd4",
    "action": "#00b894",
    "strategy": "#fdcb6e",
    "simulation": "#00cec9",
    "platformer": "#fd79a8",
    "horror": "#2d3436",
    "roguelike": "#a29bfe",
    "survival": "#55a084",
    "racing": "#e84393",
    "fighting": "#ff7675",
    "puzzle": "#74b9ff",
    "mmo": "#6c5ce7",
    "multiplayer": "#00b894",
    "singleplayer": "#4a6cd4",
    "coop": "#fdcb6e",
    "open world": "#e17055",
}

import tkinter.font as tkfont


def _family():
    try:
        return tkfont.nametofont("TkDefaultFont").actual("family")
    except Exception:
        return "TkDefaultFont"


def font(size, bold=False):
    return tkfont.Font(family=_family(), size=size, weight="bold" if bold else "normal")


def load_fonts():
    return {
        "title": font(12, True),
        "h1": font(11, True),
        "card_name": font(10),
        "card_name_bold": font(10, True),
        "badge": font(7, True),
        "dim": font(8),
        "playtime": font(8),
        "menu": font(9),
        "stat_icon": font(18),
        "stat_count": font(26, True),
        "stat_label": font(9),
        "play_btn": font(9, True),
        "info_title": font(14, True),
        "info_label": font(9),
        "info_value": font(9),
        "info_dim": font(8),
        "info_btn": font(11, True),
        "star": font(14),
    }


def fmt_playtime(seconds):
    try:
        seconds = int(seconds or 0)
    except (ValueError, TypeError):
        seconds = 0
    h, rem = divmod(seconds, 3600)
    m = rem // 60
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def fmt_last_played(ts):
    if not ts:
        return "Never"
    import time
    try:
        ts = int(ts)
    except (ValueError, TypeError):
        return "Never"
    diff = int(time.time()) - ts
    if diff < 60:
        return "Just now"
    if diff < 3600:
        return f"{diff // 60}m ago"
    if diff < 86400:
        return f"{diff // 3600}h ago"
    days = diff // 86400
    if days == 1:
        return "Yesterday"
    if days < 30:
        return f"{days}d ago"
    if days < 365:
        return f"{days // 30}mo ago"
    return f"{days // 365}y ago"


def rounded_rect(canvas, x1, y1, x2, y2, r, **kw):
    points = [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1, x2, y1 + r,
        x2, y2 - r,
        x2, y2, x2 - r, y2,
        x1 + r, y2,
        x1, y2, x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]
    return canvas.create_polygon(points, smooth=True, **kw)


def truncate(text, max_len=22):
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "\u2026"
