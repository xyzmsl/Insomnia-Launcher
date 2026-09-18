import tkinter as tk
from PIL import Image, ImageTk

from . import theme
from .theme import (BG_CARD, BG_CARD_HOVER, TEXT, TEXT_DIM, STAR_ON, STAR_OFF,
                     ACCENT, ACCENT_GREEN, CARD_BORDER, CARD_HOVER_BORDER,
                     SOURCE_COLORS)

_blank_cache = {}


def _blank_img(size):
    key = size
    if key not in _blank_cache:
        img = Image.new("RGB", size, tuple(int(theme.BG_DARK.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)))
        _blank_cache[key] = ImageTk.PhotoImage(img)
    return _blank_cache[key]


class GameCard(tk.Frame):
    def __init__(self, master, game, store, callbacks, fonts):
        super().__init__(master, bg=CARD_BORDER, highlightthickness=0, bd=0)
        self.game = game
        self.gid = game["id"]
        self.store = store
        self.callbacks = callbacks
        self.fonts = fonts
        self.photo = None
        self._selected = False

        self._inner = tk.Frame(self, bg=BG_CARD, highlightthickness=0, bd=0)
        self._inner.pack(fill="both", expand=True, padx=1, pady=1)

        self._cover_frame = tk.Frame(self._inner, bg=BG_CARD, highlightthickness=0, bd=0)
        self._cover_frame.pack(fill="x")

        self._img = tk.Label(self._cover_frame, bg=BG_CARD, image=_blank_img(theme.CARD_IMG_SIZE), anchor="center")
        self._img.pack(fill="x")

        self._star = tk.Label(
            self._cover_frame, text="\u2605", bg=BG_CARD,
            fg=STAR_ON if game.get("favorite") else STAR_OFF,
            font=fonts["star"], cursor="hand2",
        )
        self._star.place(relx=1.0, rely=0.0, x=-6, y=4, anchor="ne")
        self._star.bind("<Button-1>", self._on_fav_click)
        self._star.bind("<Enter>", lambda e: self._star.configure(fg=ACCENT))
        self._star.bind("<Leave>", lambda e: self._star.configure(
            fg=STAR_ON if self.game.get("favorite") else STAR_OFF))

        name_row = tk.Frame(self._inner, bg=BG_CARD, highlightthickness=0, bd=0)
        name_row.pack(fill="x", padx=8, pady=(6, 0))
        self._name = tk.Label(
            name_row, bg=BG_CARD,
            text=theme.truncate(game["name"], 22), fg=TEXT,
            font=fonts["card_name"], anchor="w", justify="left",
        )
        self._name.pack(side="left", fill="x", expand=True)

        meta = tk.Frame(self._inner, bg=BG_CARD, highlightthickness=0, bd=0)
        meta.pack(fill="x", padx=8, pady=(2, 0))
        badge_bg = SOURCE_COLORS.get(game["source"], "#333")
        self._badge = tk.Label(
            meta, bg=badge_bg, text=game["source"].title(),
            fg="#ffffff", font=fonts["badge"], padx=4, pady=0,
        )
        self._badge.pack(side="left")

        self._playtime = tk.Label(
            meta, bg=BG_CARD, text="", fg=TEXT_DIM,
            font=fonts["playtime"], anchor="w",
        )
        self._playtime.pack(side="left", padx=(6, 0))

        btn_frame = tk.Frame(self._inner, bg=BG_CARD, highlightthickness=0, bd=0)
        btn_frame.pack(fill="x", padx=8, pady=(6, 8))

        self._play_btn = tk.Button(
            btn_frame, text="\u25b6  Play", bg=ACCENT_GREEN, fg="white",
            activebackground=ACCENT_GREEN, activeforeground="white",
            font=fonts["play_btn"], relief="flat", bd=0, highlightthickness=0,
            highlightbackground=ACCENT_GREEN, highlightcolor=ACCENT_GREEN,
            cursor="hand2", padx=12, pady=3,
            command=lambda: self.callbacks["launch"](self.game),
        )
        self._play_btn.pack(fill="x")

        self._cover_frame.bind("<Button-1>", self._on_card_click)
        self._img.bind("<Button-1>", self._on_card_click)
        self._name.bind("<Button-1>", self._on_card_click)
        meta.bind("<Button-1>", self._on_card_click)
        self._inner.bind("<Button-1>", self._on_card_click)
        self.bind("<Button-1>", self._on_card_click)

        self._cover_frame.bind("<Button-3>", lambda e: self.callbacks["menu"](self.game, e))
        self._img.bind("<Button-3>", lambda e: self.callbacks["menu"](self.game, e))
        self._name.bind("<Button-3>", lambda e: self.callbacks["menu"](self.game, e))

        self._inner.bind("<Enter>", lambda e: self._on_enter())
        self._inner.bind("<Leave>", lambda e: self._on_leave())

        self.set_playtime(self.callbacks["stats"].get(self.gid, {}).get("playtime", 0))

    def set_selected(self, selected):
        self._selected = selected
        if selected:
            self.configure(bg=CARD_HOVER_BORDER)
            self._inner.configure(bg=BG_CARD_HOVER)
            for w in (self._cover_frame, self._img, self._name):
                try:
                    w.configure(bg=BG_CARD_HOVER)
                except tk.TclError:
                    pass
        else:
            self.configure(bg=CARD_BORDER)
            self._inner.configure(bg=BG_CARD)
            for w in (self._cover_frame, self._img, self._name):
                try:
                    w.configure(bg=BG_CARD)
                except tk.TclError:
                    pass

    def set_playtime(self, seconds):
        pt = theme.fmt_playtime(seconds)
        self._playtime.config(text=pt if pt != "0m" else "0m")

    def set_cover(self, photo, size):
        self.photo = photo
        self._img.config(image=photo, width=size[0], height=size[1])

    def set_placeholder_text(self, text, size=None):
        blank = _blank_img(size) if size else None
        if size:
            self._img.config(image=blank, text="", width=size[0], height=size[1])
        else:
            self._img.config(image="", text=text, width=0, height=0)

    def _on_card_click(self, _event):
        self.callbacks["select"](self.game)

    def _on_fav_click(self, _event):
        self.callbacks["favorite"](self.game)

    def _on_enter(self):
        if not self._selected:
            self.configure(bg=CARD_HOVER_BORDER)
            self._inner.configure(bg=BG_CARD_HOVER)
            for w in (self._cover_frame, self._img, self._name, self._playtime, self._badge):
                try:
                    w.configure(bg=BG_CARD_HOVER)
                except tk.TclError:
                    pass

    def _on_leave(self):
        if not self._selected:
            self.configure(bg=CARD_BORDER)
            self._inner.configure(bg=BG_CARD)
            for w in (self._cover_frame, self._img, self._name, self._playtime, self._badge):
                try:
                    w.configure(bg=BG_CARD)
                except tk.TclError:
                    pass
