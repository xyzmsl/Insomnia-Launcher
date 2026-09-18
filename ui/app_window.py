import os
import queue
import subprocess
import sys
import threading
import time

import tkinter as tk
from tkinter import ttk, messagebox
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageTk

from app import config
from app import launch as launch_mod
from app import updater
from app import metrics
from app.coverart import fetch_one
from app.detectors import detect_all
from app.models import Game
from app.store import Store
from app.version import __version__
from . import theme
from .cards import GameCard
from .dialogs import AddGameDialog, SettingsDialog

CARD_W = 215
CARD_IMG = theme.CARD_IMG_SIZE
PAD = 8
STAT_H = 70
SCROLLBAR_W = 17
ASSETS = os.path.join(os.path.dirname(__file__), "assets")

SOURCE_ORDER = ["steam", "epic", "gog", "flatpak", "local", "ea"]
SORT_OPTIONS = {
    "Name": "name",
    "Recently played": "recent",
    "Playtime": "playtime",
    "Source": "source",
    "Recently added": "added",
}
GENRE_OPTIONS = [
    "All genres",
    "Action", "Co-op", "Fighting", "Horror", "MMO", "MMORPG",
    "Multiplayer", "Open World", "Platformer", "Puzzle",
    "Racing", "Roguelike", "RPG", "Shooter",
    "Simulation", "Singleplayer", "Strategy", "Survival",
]

NAV_ITEMS = [
    ("All games", "all"),
    ("Favorites", "fav"),
    ("Recently played", "recent"),
]


def _load_icon(name):
    path = os.path.join(ASSETS, f"icon_{name}.png")
    if os.path.isfile(path):
        return ImageTk.PhotoImage(Image.open(path).resize((16, 16), Image.LANCZOS))
    return None


class StatCard(tk.Canvas):
    def __init__(self, parent, color, icon, label, fonts, bg=theme.BG):
        super().__init__(parent, height=STAT_H, bg=bg, highlightthickness=0, bd=0)
        self._color = color
        self._icon = icon
        self._label = label
        self._count = 0
        self._fonts = fonts
        self.bind("<Configure>", lambda e: self._draw())

    def set_count(self, count):
        self._count = count
        self._draw()

    def _draw(self):
        self.delete("all")
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 30 or h < 30:
            return
        r = 10
        theme.rounded_rect(self, 2, 2, w - 2, h - 2, r, fill=self._color, outline="")
        self.create_text(14, h // 2 - 8, text=self._icon, font=self._fonts["stat_icon"],
                         anchor="w", fill="white")
        self.create_text(38, h // 2 - 12, text=str(self._count),
                         font=self._fonts["stat_count"], anchor="w", fill="white")
        self.create_text(38, h // 2 + 10, text=self._label,
                         font=self._fonts["stat_label"], anchor="w", fill="#dde4ee")


class AppWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.configure(bg=theme.BG)
        self.title(f"Insomnia Launcher v{__version__}")
        self.minsize(760, 480)
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        w, h = 1180, 760
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.fonts = theme.load_fonts()
        self._source_icons = {}
        for name in SOURCE_ORDER:
            self._source_icons[name] = _load_icon(name)

        self.settings = config.load_settings()
        self.store = Store(config.DB_PATH)
        self.games = []
        self.stats_cache = {}
        self.mode = self.settings.get("mode", "all")
        self.source_filter = self.settings.get("source_filter")
        self.genre_filter = self.settings.get("genre_filter")
        self.search_text = self.settings.get("search_text", "")
        self.sort_key = self.settings.get("sort_key", "name")
        self._cover_pil = {}
        self._cover_queue = queue.Queue()
        self._card_by_gid = {}
        self._columns = 1
        self._visible_ids = []
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._events = queue.Queue()
        self._closed = False
        self._stat_cards = {}
        self._selected_game = None
        self._info_visible = False
        self._info_cover_photo = None
        self._info_cover_pil = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(60, self._poll_covers)
        self.bind("<Configure>", self._on_global_resize)
        self.refresh_from_db()
        self.rescan()
        if self.settings.get("auto_update"):
            self.after(1200, self._check_update_on_startup)

    def _build_ui(self):
        self.configure(bg=theme.BG)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=theme.BG, foreground=theme.TEXT, borderwidth=0, relief="flat")
        style.configure("TFrame", background=theme.BG, borderwidth=0, relief="flat")
        style.configure("TLabel", background=theme.BG, foreground=theme.TEXT, borderwidth=0, relief="flat")
        style.configure("TButton", background=theme.BG_CARD, foreground=theme.TEXT, borderwidth=0, relief="flat")
        style.configure("TEntry", background=theme.BG_CARD, foreground=theme.TEXT, borderwidth=0, relief="flat",
                         fieldbackground=theme.BG_CARD)
        style.configure("TCombobox", fieldbackground=theme.BG_CARD, background=theme.BG_CARD,
                         foreground=theme.TEXT, borderwidth=0, relief="flat",
                         darkcolor=theme.BG_CARD, lightcolor=theme.BG_CARD,
                         selectbackground=theme.BG_CARD, selectforeground=theme.TEXT,
                         focuscolor=theme.BG_CARD, padding=4)
        style.configure("TCombobox.Downarrow.TButton", background=theme.BG_CARD,
                         borderwidth=0, relief="flat", arrowcolor=theme.TEXT_DIM)
        style.map("TCombobox", fieldbackground=[("readonly", theme.BG_CARD)],
                  borderwidth=[("active", 0), ("pressed", 0), ("readonly", 0)],
                  lightcolor=[("active", theme.BG_CARD), ("pressed", theme.BG_CARD)],
                  darkcolor=[("active", theme.BG_CARD), ("pressed", theme.BG_CARD)])
        style.configure("TScrollbar", background=theme.BG_SIDE, troughcolor=theme.BG,
                         borderwidth=0, relief="flat", arrowcolor=theme.TEXT_DIM)
        self.option_add("*Entry.highlightThickness", 0)
        self.option_add("*Entry.bd", 0)
        self.option_add("*Label.bd", 0)
        self.option_add("*Button.bd", 0)
        self.option_add("*Frame.bd", 0)
        self.option_add("*Canvas.highlightThickness", 0)
        self.option_add("*Canvas.bd", 0)
        self.option_add("*TCombobox*Listbox.background", theme.BG_CARD)
        self.option_add("*TCombobox*Listbox.foreground", theme.TEXT)
        self.option_add("*TCombobox*Listbox.selectBackground", theme.ACCENT)
        self.option_add("*TCombobox*Listbox.selectForeground", "white")
        self._build_header()
        self._build_body()
        self._build_statusbar()
        self._build_menu()

    def _build_header(self):
        head = tk.Frame(self, bg=theme.BG_SIDE, height=48)
        head.pack(fill="x", side="top")
        head.pack_propagate(False)

        left = tk.Frame(head, bg=theme.BG_SIDE)
        left.pack(side="left", fill="y", padx=10)
        tk.Label(left, text="\U0001f3ae  Insomnia Launcher", bg=theme.BG_SIDE, fg=theme.TEXT_HEADER,
                 font=theme.font(10, True)).pack(side="left", pady=0)

        center = tk.Frame(head, bg=theme.BG_SIDE)
        center.pack(side="left", fill="y", expand=True)

        self._search_var = tk.StringVar(value=self.search_text)
        self._search_var.trace_add("write", lambda *a: self._on_search())
        search_frame = tk.Frame(center, bg=theme.BG_CARD, bd=0, highlightthickness=0)
        search_frame.pack(side="left", pady=8)
        tk.Label(search_frame, text=" \U0001f50d ", bg=theme.BG_CARD, fg=theme.TEXT_DIM,
                 font=theme.font(8), bd=0, highlightthickness=0).pack(side="left")
        self._search_entry = tk.Entry(
            search_frame, textvariable=self._search_var, bg=theme.BG_CARD, fg=theme.TEXT,
            insertbackground=theme.TEXT, relief="flat", font=theme.font(9), width=16,
            bd=0, highlightthickness=0,
        )
        self._search_entry.pack(side="left", padx=(0, 8), pady=2)

        self._sort_var = tk.StringVar(value="Name")
        sort_frame = tk.Frame(center, bg=theme.BG_SIDE, bd=0, highlightthickness=0)
        sort_frame.pack(side="left", padx=(0, 6), pady=8)
        tk.Label(sort_frame, text="Sort:", bg=theme.BG_SIDE, fg=theme.TEXT_DIM,
                 font=theme.font(8), bd=0, highlightthickness=0).pack(side="left")
        sort_combo = ttk.Combobox(sort_frame, textvariable=self._sort_var, values=list(SORT_OPTIONS),
                                  state="readonly", width=13)
        sort_combo.pack(side="left", padx=3)
        sort_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_sort())

        self._genre_var = tk.StringVar(value="All genres")
        genre_frame = tk.Frame(center, bg=theme.BG_SIDE, bd=0, highlightthickness=0)
        genre_frame.pack(side="left", padx=(0, 6), pady=8)
        tk.Label(genre_frame, text="Genre:", bg=theme.BG_SIDE, fg=theme.TEXT_DIM,
                 font=theme.font(8), bd=0, highlightthickness=0).pack(side="left")
        genre_combo = ttk.Combobox(genre_frame, textvariable=self._genre_var, values=GENRE_OPTIONS,
                                   state="readonly", width=14)
        genre_combo.pack(side="left", padx=3)
        genre_combo.bind("<<ComboboxSelected>>", lambda e: self._apply_genre())

        right = tk.Frame(head, bg=theme.BG_SIDE, bd=0, highlightthickness=0)
        right.pack(side="right", fill="y", padx=10)

        btn_kw = dict(relief="flat", bd=0, highlightthickness=0, font=theme.font(9), cursor="hand2", padx=8, pady=3)
        tk.Button(right, text="+ Game", bg=theme.BG_CARD, fg=theme.TEXT,
                  activebackground=theme.BG_CARD_HOVER, activeforeground=theme.TEXT,
                  command=self._open_add_game, **btn_kw).pack(side="left", padx=2, pady=8)
        tk.Button(right, text="Refresh", bg=theme.ACCENT, fg="white",
                  activebackground=theme.ACCENT_DIM, command=self.rescan, **btn_kw).pack(side="left", padx=2, pady=8)
        tk.Button(right, text="Settings", bg=theme.BG_CARD, fg=theme.TEXT,
                  activebackground=theme.BG_CARD_HOVER, activeforeground=theme.TEXT,
                  command=self._open_settings, **btn_kw).pack(side="left", padx=2, pady=8)

    def _build_body(self):
        body = tk.Frame(self, bg=theme.BG, bd=0, highlightthickness=0)
        body.pack(fill="both", expand=True, side="top")

        self._sidebar = tk.Frame(body, bg=theme.BG_SIDE, width=150, bd=0, highlightthickness=0)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        tk.Label(self._sidebar, text="LIBRARY", bg=theme.BG_SIDE, fg=theme.TEXT_DIM,
                 font=theme.font(7, True), anchor="w", bd=0, highlightthickness=0).pack(fill="x", padx=12, pady=(12, 6))

        self._nav_buttons = {}
        for label, key in NAV_ITEMS:
            b = self._make_nav_button(label, lambda k=key: self._set_mode(k))
            b.pack(fill="x", padx=6, pady=1)
            self._nav_buttons[key] = b

        sep = tk.Frame(self._sidebar, bg=theme.BORDER, height=1, bd=0, highlightthickness=0)
        sep.pack(fill="x", padx=10, pady=(10, 0))

        tk.Label(self._sidebar, text="SOURCES", bg=theme.BG_SIDE, fg=theme.TEXT_DIM,
                 font=theme.font(7, True), anchor="w", bd=0, highlightthickness=0).pack(fill="x", padx=12, pady=(10, 6))

        self._source_buttons = {}
        for src in SOURCE_ORDER:
            b = self._make_nav_button(src.title(), lambda s=src: self._set_source(s), src)
            b.pack(fill="x", padx=6, pady=1)
            self._source_buttons[src] = b

        b = self._make_nav_button("All sources", lambda: self._set_source(None))
        b.pack(fill="x", padx=6, pady=1)
        self._nav_buttons["allsrc"] = b

        self._main_content = tk.Frame(body, bg=theme.BG, bd=0, highlightthickness=0)
        self._main_content.pack(side="left", fill="both", expand=True)
        self._main_content.columnconfigure(0, weight=1)
        self._main_content.rowconfigure(0, weight=1)

        self._grid_area = tk.Frame(self._main_content, bg=theme.BG, bd=0, highlightthickness=0)
        self._grid_area.grid(row=0, column=0, sticky="nsew")

        stat_row = tk.Frame(self._grid_area, bg=theme.BG, bd=0, highlightthickness=0)
        stat_row.pack(fill="x", padx=10, pady=(10, 6))

        stat_defs = [
            ("total", theme.STAT_GREEN, "\U0001f3ae", "Total"),
            ("steam", theme.STAT_BLUE, "\u26a1", "Steam"),
            ("epic", theme.STAT_ORANGE, "\U0001f3c6", "Epic"),
            ("fav", theme.STAT_PURPLE, "\u2b50", "Favorites"),
        ]
        for key, color, icon, label in stat_defs:
            card = StatCard(stat_row, color, icon, label, self.fonts, bg=theme.BG)
            card.pack(side="left", fill="x", expand=True, padx=3)
            self._stat_cards[key] = card

        grid_frame = tk.Frame(self._grid_area, bg=theme.BG, bd=0, highlightthickness=0)
        grid_frame.pack(fill="both", expand=True, padx=10, pady=(2, 4))

        self._canvas = tk.Canvas(grid_frame, bg=theme.BG, highlightthickness=0, bd=0)
        scrollbar = ttk.Scrollbar(grid_frame, orient="vertical", command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self._canvas.pack(side="left", fill="both", expand=True)
        self._cards_frame = tk.Frame(self._canvas, bg=theme.BG, bd=0, highlightthickness=0)
        self._window_id = self._canvas.create_window((0, 0), window=self._cards_frame, anchor="nw")
        self._cards_frame.bind("<Configure>", self._on_frame_configure)
        self._canvas.bind("<Configure>", self._on_canvas_configure)
        self._bind_mousewheel()

        self._info_panel = tk.Frame(self._main_content, bg=theme.INFO_BG, width=theme.INFO_WIDTH,
                                     bd=0, highlightthickness=0)
        self._info_panel.grid_propagate(False)
        self._info_panel.grid(row=0, column=1, sticky="ns")
        self._info_panel.grid_remove()

    def _build_statusbar(self):
        self._status = tk.Label(
            self, text="Ready", bg=theme.BG_SIDE, fg=theme.TEXT_DIM, anchor="w",
            font=theme.font(7), padx=12, pady=3, bd=0, highlightthickness=0,
        )
        self._status.pack(fill="x", side="bottom")

    def _build_menu(self):
        self._menu_obj = tk.Menu(self, tearoff=0, bg=theme.BG_CARD, fg=theme.TEXT,
                                 activebackground=theme.ACCENT, activeforeground="white",
                                 font=self.fonts["menu"])
        self._menu_obj.add_command(label="Play", command=lambda: self._menu_game and self.launch_game(self._menu_game))
        self._menu_obj.add_command(label="Toggle favorite", command=self._menu_toggle_fav)
        self._menu_obj.add_command(label="Open folder", command=self._menu_open_folder)
        self._menu_obj.add_separator()
        self._genre_menu = tk.Menu(self._menu_obj, tearoff=0, bg=theme.BG_CARD, fg=theme.TEXT,
                                    activebackground=theme.ACCENT, activeforeground="white",
                                    font=self.fonts["menu"])
        self._menu_obj.add_cascade(label="Set genre", menu=self._genre_menu)
        self._genre_menu.add_command(label="None", command=lambda: self._menu_set_genre(""))
        for genre in ["Action", "Co-op", "Fighting", "Horror", "MMO", "MMORPG",
                       "Multiplayer", "Open World", "Platformer", "Puzzle",
                       "Racing", "Roguelike", "RPG", "Shooter", "Simulation",
                       "Singleplayer", "Strategy", "Survival"]:
            self._genre_menu.add_command(label=genre,
                                         command=lambda g=genre.lower(): self._menu_set_genre(g))
        self._menu_obj.add_separator()
        self._menu_obj.add_command(label="Hide", command=self._menu_hide)
        self._menu_game = None

    def _make_nav_button(self, label, command, source_key=None):
        icon_img = self._source_icons.get(source_key) if source_key else None
        if icon_img:
            b = tk.Button(
                self._sidebar, text=f"  {label}", image=icon_img, compound="left",
                command=command, bd=0, highlightthickness=0, relief="flat",
                bg=theme.BG_SIDE, fg=theme.TEXT_DIM, activebackground=theme.BG_CARD,
                activeforeground=theme.TEXT, anchor="w", padx=8, pady=5,
                font=theme.font(9), cursor="hand2",
            )
        else:
            b = tk.Button(
                self._sidebar, text=f"   {label}", command=command, bd=0, highlightthickness=0, relief="flat",
                bg=theme.BG_SIDE, fg=theme.TEXT_DIM, activebackground=theme.BG_CARD,
                activeforeground=theme.TEXT, anchor="w", padx=8, pady=5,
                font=theme.font(9), cursor="hand2",
            )
        b.bind("<Enter>", lambda e, b=b: b.configure(bg=theme.BG_CARD) if not getattr(b, "_active", False) else None)
        b.bind("<Leave>", lambda e, b=b: b.configure(bg=theme.ACCENT) if getattr(b, "_active", False) else b.configure(bg=theme.BG_SIDE))
        return b

    def _set_active_nav(self):
        for key, b in self._nav_buttons.items():
            active = (key == self.mode or (key == "allsrc" and self.source_filter is None))
            b._active = active
            b.configure(bg=theme.ACCENT if active else theme.BG_SIDE, fg="white" if active else theme.TEXT_DIM)
        for src, b in self._source_buttons.items():
            active = self.source_filter == src
            b._active = active
            b.configure(bg=theme.ACCENT if active else theme.BG_SIDE, fg="white" if active else theme.TEXT_DIM)

    def _bind_mousewheel(self):
        def on_wheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def on_wheel_x11(event):
            if event.num == 4:
                self._canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self._canvas.yview_scroll(1, "units")

        self._canvas.bind("<Enter>", lambda e: (
            self._canvas.bind_all("<MouseWheel>", on_wheel),
            self._canvas.bind_all("<Button-4>", on_wheel_x11),
            self._canvas.bind_all("<Button-5>", on_wheel_x11),
        ))
        self._canvas.bind("<Leave>", lambda e: (
            self._canvas.unbind_all("<MouseWheel>"),
            self._canvas.unbind_all("<Button-4>"),
            self._canvas.unbind_all("<Button-5>"),
        ))

    def _on_frame_configure(self, _event):
        self._canvas.configure(scrollregion=self._canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        self._canvas.itemconfig(self._window_id, width=event.width)
        self._schedule_reflow()

    def _on_global_resize(self, _event):
        self._schedule_reflow()

    def _schedule_reflow(self):
        if hasattr(self, "_resize_job"):
            try:
                self.after_cancel(self._resize_job)
            except Exception:
                pass
        self._resize_job = self.after(100, self._reflow)

    def _set_mode(self, mode):
        self.mode = mode
        self._set_active_nav()
        self._reflow()
        self._persist_filters()

    def _set_source(self, source):
        self.source_filter = source
        self._set_active_nav()
        self._reflow()
        self._persist_filters()

    def _apply_genre(self):
        val = self._genre_var.get()
        if val == "All genres":
            self.genre_filter = None
        else:
            self.genre_filter = val.lower()
        self._reflow()
        self._persist_filters()

    def _apply_sort(self):
        self.sort_key = SORT_OPTIONS.get(self._sort_var.get(), "name")
        self._reflow()
        self._persist_filters()

    def _on_search(self):
        self.search_text = self._search_var.get().strip().lower()
        self._reflow()
        self._persist_filters()

    def _persist_filters(self):
        self.settings.update(
            {
                "mode": self.mode,
                "source_filter": self.source_filter,
                "genre_filter": self.genre_filter,
                "search_text": self.search_text,
                "sort_key": self.sort_key,
            }
        )
        config.save_settings(self.settings)

    def _open_settings(self):
        SettingsDialog(self, self.settings, self._save_settings, self.rescan)

    def _save_settings(self, new_settings):
        self.settings.update(new_settings)
        config.save_settings(self.settings)

    def _open_add_game(self):
        AddGameDialog(self, self._add_game)

    def _add_game(self, game):
        self.store.add_manual(game)
        self.refresh_from_db()

    def _menu(self, game, event):
        if not hasattr(self, "_menu_obj"):
            return
        self._menu_game = game
        try:
            self._menu_obj.tk_popup(event.x_root, event.y_root)
        finally:
            self._menu_obj.grab_release()

    def _menu_toggle_fav(self):
        if self._menu_game:
            self.toggle_favorite(self._menu_game)

    def _menu_set_genre(self, genre):
        g = self._menu_game
        if g:
            self.store.set_genre(g["id"], genre)
            g["genre"] = genre
            self._reflow()

    def _menu_open_folder(self):
        g = self._menu_game
        if not g:
            return
        folder = g.get("install_dir") or os.path.dirname(g.get("exe") or "")
        if not folder or not os.path.isdir(folder):
            self._set_status(f"Folder not found for {g['name']}")
            return
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _menu_hide(self):
        g = self._menu_game
        if g:
            self.store.set_hidden(g["id"], True)
            self.refresh_from_db()

    def _select_game(self, game):
        if self._selected_game and self._selected_game["id"] == game["id"]:
            self._hide_info()
            return
        self._selected_game = game
        self._show_info(game)
        for gid, card in self._card_by_gid.items():
            card.set_selected(gid == game["id"])

    def _show_info(self, game):
        for w in self._info_panel.winfo_children():
            w.destroy()
        self._info_visible = True
        self._info_panel.grid()

        top = tk.Frame(self._info_panel, bg=theme.INFO_BG, bd=0, highlightthickness=0)
        top.pack(fill="x")

        close_btn = tk.Button(
            top, text="\u2715", bg=theme.INFO_BG, fg=theme.TEXT_DIM,
            font=theme.font(10), bd=0, highlightthickness=0, relief="flat",
            cursor="hand2", command=self._hide_info, padx=8, pady=2,
        )
        close_btn.pack(side="right", padx=8, pady=8)
        close_btn.bind("<Enter>", lambda e: close_btn.configure(fg=theme.TEXT))
        close_btn.bind("<Leave>", lambda e: close_btn.configure(fg=theme.TEXT_DIM))

        cover_frame = tk.Frame(self._info_panel, bg=theme.BG_DARK, bd=0, highlightthickness=0)
        cover_frame.pack(fill="x", padx=0, pady=0)

        self._info_cover_label = tk.Label(cover_frame, bg=theme.BG_DARK, anchor="center")
        self._info_cover_label.pack(fill="x")

        pil = self._cover_pil.get(game["id"])
        if pil:
            resized = pil.resize((theme.INFO_WIDTH, 180), Image.LANCZOS)
            self._info_cover_pil = resized
            self._info_cover_photo = ImageTk.PhotoImage(resized)
            self._info_cover_label.config(image=self._info_cover_photo, width=theme.INFO_WIDTH, height=180)
        else:
            self._info_cover_label.config(text="No cover art", fg=theme.TEXT_DIM,
                                           font=theme.font(9), height=8)

        info_body = tk.Frame(self._info_panel, bg=theme.INFO_BG, bd=0, highlightthickness=0)
        info_body.pack(fill="both", expand=True, padx=14, pady=10)

        tk.Label(info_body, text=theme.truncate(game["name"], 30), bg=theme.INFO_BG,
                 fg=theme.TEXT_HEADER, font=self.fonts["info_title"],
                 anchor="w", wraplength=theme.INFO_WIDTH - 28).pack(fill="x", pady=(0, 6))

        detail_row = tk.Frame(info_body, bg=theme.INFO_BG, bd=0, highlightthickness=0)
        detail_row.pack(fill="x", pady=(0, 4))
        badge_bg = theme.SOURCE_COLORS.get(game["source"], "#333")
        tk.Label(detail_row, text=game["source"].title(), bg=badge_bg, fg="white",
                 font=theme.font(7, True), padx=5, pady=1).pack(side="left")
        if game.get("genre"):
            genre_text = game["genre"].replace(",", ", ").title()
            tk.Label(detail_row, text=f"  {genre_text}", bg=theme.INFO_BG, fg=theme.TEXT_DIM,
                     font=theme.font(8)).pack(side="left", padx=(4, 0))

        sep1 = tk.Frame(info_body, bg=theme.BORDER, height=1, bd=0, highlightthickness=0)
        sep1.pack(fill="x", pady=(10, 8))

        playtime_val = theme.fmt_playtime(self.stats_cache["playtime"].get(game["id"], 0))
        last_played_val = theme.fmt_last_played(self.stats_cache["last_played"].get(game["id"]))

        stats_frame = tk.Frame(info_body, bg=theme.INFO_BG, bd=0, highlightthickness=0)
        stats_frame.pack(fill="x", pady=(0, 4))
        tk.Label(stats_frame, text="Playtime", bg=theme.INFO_BG, fg=theme.TEXT_DIM,
                 font=theme.font(8), anchor="w").pack(side="left")
        tk.Label(stats_frame, text=playtime_val, bg=theme.INFO_BG, fg=theme.TEXT,
                 font=theme.font(9, True), anchor="e").pack(side="right")

        stats_frame2 = tk.Frame(info_body, bg=theme.INFO_BG, bd=0, highlightthickness=0)
        stats_frame2.pack(fill="x", pady=(0, 4))
        tk.Label(stats_frame2, text="Last played", bg=theme.INFO_BG, fg=theme.TEXT_DIM,
                 font=theme.font(8), anchor="w").pack(side="left")
        tk.Label(stats_frame2, text=last_played_val, bg=theme.INFO_BG, fg=theme.TEXT,
                 font=theme.font(9), anchor="e").pack(side="right")

        sep2 = tk.Frame(info_body, bg=theme.BORDER, height=1, bd=0, highlightthickness=0)
        sep2.pack(fill="x", pady=(10, 10))

        play_btn = tk.Button(
            info_body, text="\u25b6  Play Game", bg=theme.ACCENT_GREEN, fg="white",
            activebackground=theme.ACCENT_GREEN, activeforeground="white",
            font=self.fonts["info_btn"], relief="flat", bd=0, highlightthickness=0,
            highlightbackground=theme.ACCENT_GREEN, highlightcolor=theme.ACCENT_GREEN,
            cursor="hand2", padx=12, pady=8,
            command=lambda: self.launch_game(game),
        )
        play_btn.pack(fill="x", pady=(0, 8))

        fav_text = "\u2605 Remove from Favorites" if game.get("favorite") else "\u2606 Add to Favorites"
        fav_btn = tk.Button(
            info_body, text=fav_text, bg=theme.BG_CARD, fg=theme.TEXT,
            activebackground=theme.BG_CARD_HOVER, activeforeground=theme.TEXT,
            font=theme.font(9), relief="flat", bd=0, highlightthickness=0,
            cursor="hand2", padx=8, pady=5,
            command=lambda: self._info_toggle_fav(game),
        )
        fav_btn.pack(fill="x", pady=(0, 4))

        folder_btn = tk.Button(
            info_body, text="\U0001f4c2  Open Install Folder", bg=theme.BG_CARD, fg=theme.TEXT_DIM,
            activebackground=theme.BG_CARD_HOVER, activeforeground=theme.TEXT,
            font=theme.font(8), relief="flat", bd=0, highlightthickness=0,
            cursor="hand2", padx=8, pady=4,
            command=lambda: self._info_open_folder(game),
        )
        folder_btn.pack(fill="x", pady=(0, 4))

        hide_btn = tk.Button(
            info_body, text="\u2716  Hide Game", bg=theme.INFO_BG, fg=theme.TEXT_DIM,
            activebackground=theme.BG_CARD, activeforeground=theme.TEXT,
            font=theme.font(8), relief="flat", bd=0, highlightthickness=0,
            cursor="hand2", padx=8, pady=4,
            command=lambda: self._info_hide_game(game),
        )
        hide_btn.pack(fill="x", pady=(4, 0))

        self._schedule_reflow()

    def _hide_info(self):
        self._info_visible = False
        self._selected_game = None
        self._info_panel.grid_remove()
        for card in self._card_by_gid.values():
            card.set_selected(False)
        self._schedule_reflow()

    def _info_toggle_fav(self, game):
        self.toggle_favorite(game)
        if self._selected_game and self._selected_game["id"] == game["id"]:
            self._show_info(game)

    def _info_open_folder(self, game):
        folder = game.get("install_dir") or os.path.dirname(game.get("exe") or "")
        if not folder or not os.path.isdir(folder):
            self._set_status(f"Folder not found for {game['name']}")
            return
        if sys.platform == "win32":
            os.startfile(folder)
        else:
            subprocess.Popen(["xdg-open", folder], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _info_hide_game(self, game):
        self.store.set_hidden(game["id"], True)
        self._hide_info()
        self.refresh_from_db()

    def refresh_from_db(self):
        self.games = self.store.all_games()
        self.stats_cache = {
            "playtime": self.store.playtime_map(),
            "last_played": self.store.last_played_map(),
        }
        self._set_active_nav()
        self._update_stat_cards()
        self._visible_ids = []
        self._reflow()
        self._update_status_counts()

    def _update_stat_cards(self):
        total = len(self.games)
        by_src = {}
        fav_count = 0
        for g in self.games:
            by_src[g["source"]] = by_src.get(g["source"], 0) + 1
            if g.get("favorite"):
                fav_count += 1
        self._stat_cards["total"].set_count(total)
        self._stat_cards["steam"].set_count(by_src.get("steam", 0))
        self._stat_cards["epic"].set_count(by_src.get("epic", 0))
        self._stat_cards["fav"].set_count(fav_count)

    def _update_status_counts(self):
        total = len(self.games)
        by_src = {}
        for g in self.games:
            by_src[g["source"]] = by_src.get(g["source"], 0) + 1
        parts = [f"{total} games"]
        for src in SOURCE_ORDER:
            if src in by_src:
                parts.append(f"{by_src[src]} {src.title()}")
        self._set_status("  \u00b7  ".join(parts))

    def _set_status(self, text):
        self._status.config(text=text)

    def visible_games(self):
        rows = []
        now = int(time.time())
        for g in self.games:
            if g.get("hidden"):
                continue
            if self.mode == "fav" and not g.get("favorite"):
                continue
            if self.mode == "recent":
                last = self.stats_cache["last_played"].get(g["id"])
                if not last or seconds_ago(last, now) > 7 * 86400:
                    continue
            if self.source_filter and g["source"] != self.source_filter:
                continue
            if self.genre_filter and self.genre_filter not in (g.get("genre") or ""):
                continue
            if self.search_text and self.search_text not in g["name"].lower():
                continue
            rows.append(g)
        self._sort_rows(rows)
        return rows

    def _sort_rows(self, rows):
        if self.sort_key == "recent":
            rows.sort(key=lambda g: self.stats_cache["last_played"].get(g["id"]) or 0, reverse=True)
        elif self.sort_key == "playtime":
            rows.sort(key=lambda g: self.stats_cache["playtime"].get(g["id"]) or 0, reverse=True)
        elif self.sort_key == "source":
            rows.sort(key=lambda g: (SOURCE_ORDER.index(g["source"]) if g["source"] in SOURCE_ORDER else 99, g["name"].lower()))
        else:
            rows.sort(key=lambda g: g["name"].lower())

    def _reflow(self):
        if not hasattr(self, "_cards_frame"):
            return
        canvas_w = self._canvas.winfo_width()
        content_w = canvas_w - SCROLLBAR_W
        if content_w < 100:
            content_w = canvas_w
        cols = max(1, (content_w + PAD) // (CARD_W + PAD))
        visible = self.visible_games()
        ids = [g["id"] for g in visible]
        if cols == self._columns and ids == self._visible_ids:
            return
        old = set(self._card_by_gid)
        new = set(ids)
        for gid in old - new:
            self._card_by_gid[gid].destroy()
            del self._card_by_gid[gid]
        for i, g in enumerate(visible):
            card = self._card_by_gid.get(g["id"])
            if card is None:
                card = self._make_card(g)
                self._card_by_gid[g["id"]] = card
            if self._selected_game and g["id"] == self._selected_game["id"]:
                card.set_selected(True)
            else:
                card.set_selected(False)
            card.grid(row=i // cols, column=i % cols, padx=4, pady=4)
        self._columns = cols
        self._visible_ids = ids
        self._ensure_covers(new - old)
        self._cards_frame.update_idletasks()

    def _make_card(self, g):
        card = GameCard(
            self._cards_frame, g, self.store,
            {
                "launch": self.launch_game,
                "favorite": self.toggle_favorite,
                "select": self._select_game,
                "menu": self._menu,
                "stats": self._card_stats(g),
            },
            self.fonts,
        )
        pil = self._cover_pil.get(g["id"])
        if pil:
            card.set_cover(ImageTk.PhotoImage(pil), CARD_IMG)
        else:
            card.set_placeholder_text("", CARD_IMG)
        return card

    def _card_stats(self, g):
        return {g["id"]: {"playtime": self.stats_cache["playtime"].get(g["id"], 0)}}

    def _ensure_covers(self, gids):
        for gid in gids:
            if gid in self._cover_pil:
                continue
            game = self.store.get(gid)
            if not game:
                continue
            self._executor.submit(self._cover_worker, game)

    def _cover_worker(self, game):
        try:
            gid, path = fetch_one(game)
            if not path or not os.path.isfile(path):
                return
            img = Image.open(path).convert("RGB")
            img = img.resize(CARD_IMG, Image.LANCZOS)
            self._cover_queue.put((gid, img))
        except Exception:
            return

    def _poll_covers(self):
        if self._closed:
            return
        try:
            while True:
                gid, img = self._cover_queue.get_nowait()
                if gid not in self._cover_pil:
                    self._cover_pil[gid] = img
                    card = self._card_by_gid.get(gid)
                    if card:
                        card.set_cover(ImageTk.PhotoImage(img), CARD_IMG)
                    if self._selected_game and gid == self._selected_game["id"]:
                        self._show_info(self._selected_game)
        except queue.Empty:
            pass
        try:
            while True:
                event = self._events.get_nowait()
                name = event[0]
                if name == "scan_done":
                    self._scan_done()
                elif name == "playtime_done":
                    self._update_game_stats(event[1])
                elif name == "status":
                    self._set_status(event[1])
                elif name == "update_available":
                    self._prompt_update(event[1])
                elif name == "apply_complete":
                    if not self._closed:
                        self.after(250, self._on_close)
        except queue.Empty:
            pass
        self.after(60, self._poll_covers)

    def _update_game_stats(self, gid):
        playtime = self.store.total_playtime(gid)
        self.stats_cache["playtime"][gid] = playtime
        last = self.store.last_played(gid)
        if last:
            self.stats_cache["last_played"][gid] = last
        card = self._card_by_gid.get(gid)
        if card:
            card.set_playtime(playtime)
        if self.mode == "recent" or self.sort_key == "playtime":
            self._reflow()

    def toggle_favorite(self, game_row):
        new_value = not game_row.get("favorite")
        self.store.set_favorite(game_row["id"], new_value)
        game_row["favorite"] = new_value
        card = self._card_by_gid.get(game_row["id"])
        if card:
            card._star.config(fg=theme.STAR_ON if new_value else theme.STAR_OFF)
        self._update_stat_cards()
        if self.mode == "fav" and not new_value:
            self._reflow()

    def launch_game(self, game_row):
        process, msg = launch_mod.launch(game_row)
        self._set_status(msg)
        gid = game_row["id"]
        metrics.start_tracking(
            self.store, gid, process,
            on_stop=lambda gid=gid: self._events.put(("playtime_done", gid)),
        )
        if process is None:
            self.stats_cache["last_played"][gid] = int(time.time())

    def rescan(self):
        self._set_status("Scanning for games...")
        threading.Thread(target=self._scan_worker, daemon=True).start()

    def _scan_worker(self):
        known_genres = {
            g["id"]: g["genre"] for g in self.store.all_games() if g.get("genre")
        }
        games = detect_all(self.settings.get("local_folders", []), known_genres=known_genres)
        from app.steam_api import get_steam_api_key, fetch_steam_playtime, apply_playtime_to_games, load_playtime_cache
        api_key = get_steam_api_key()
        plain_games = [g for g in games if g.source == "steam"]
        if api_key:
            self._events.put(("status", "Fetching Steam playtime..."))
            api_pt = fetch_steam_playtime(api_key)
            if not api_pt:
                api_pt = load_playtime_cache()
            apply_playtime_to_games(games, api_pt)
            matched = sum(1 for g in plain_games if g.playtime > 0)
            if matched:
                self._events.put(
                    ("status", f"Steam playtime synced for {matched}/{len(plain_games)} installed games")
                )
            else:
                self._events.put(("status", "Steam returned no playtime (check your API key & profile)"))
        else:
            api_pt = load_playtime_cache()
            if api_pt:
                apply_playtime_to_games(games, api_pt)
                self._events.put(("status", "Steam playtime loaded from cache"))
            else:
                self._events.put(
                    ("status", "No Steam API key — add one in Settings to fetch playtime")
                )
        self.store.upsert_games(games)
        config.save_settings(self.settings)
        self._events.put(("scan_done",))

    def _scan_done(self):
        if self._closed:
            return
        self.refresh_from_db()
        self._set_status("Scan finished.")

    def _check_update_on_startup(self):
        def worker():
            try:
                info = updater.is_newer_available(timeout=10)
            except Exception:
                info = None
            if info:
                self._events.put(("update_available", info))
        threading.Thread(target=worker, daemon=True).start()

    def _prompt_update(self, info):
        if self._closed:
            return
        version = (info or {}).get("tag_name") or "newer"
        if messagebox.askyesno(
            "New version available",
            f"Version {version} is available.\n\n"
            "Download now and install it?",
            parent=self,
        ):
            self._set_status("Downloading update...")
            threading.Thread(target=self._download_worker, daemon=True).start()

    def _download_worker(self):
        try:
            target = updater.apply_update(progress=None)
        except Exception:
            target = None
        if target:
            self._events.put(("status", "Update staged — closing to apply..."))
            self._events.put(("apply_done",))
        else:
            self._events.put(("status", "Update failed. Try again later."))

    def _relaunch_to_apply(self):
        self._on_close()

    def _on_close(self):
        self._closed = True
        self.store.close_all_open_sessions()
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
        self.destroy()


def seconds_ago(ts, now):
    return max(0, now - ts)
