import os
import threading
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox

from app import config
from app.detectors import local
from app.steam_api import get_steam_api_key, set_steam_api_key
from . import theme


def _set_color(widget, bg, fg):
    try:
        widget.configure(bg=bg, fg=fg)
    except tk.TclError:
        pass


class SettingsDialog(tk.Toplevel):
    def __init__(self, master, settings, on_save, on_rescan):
        super().__init__(master)
        self.settings = settings
        self.on_save = on_save
        self.on_rescan = on_rescan
        self.title("Settings")
        self.configure(bg=theme.BG)
        self.transient(master)
        self.resizable(False, False)

        self._build()
        self.grab_set()
        self.wait_visibility()
        self.lift()

    def _build(self):
        fonts = theme.load_fonts()
        body = tk.Frame(self, bg=theme.BG)
        body.pack(fill="both", expand=True, padx=14, pady=12)

        tk.Label(body, text="Scan folders", bg=theme.BG, fg=theme.TEXT, font=fonts["h1"]).pack(
            anchor="w"
        )
        tk.Label(
            body,
            text="Folders scanned for standalone games (.exe / .sh / .AppImage).",
            bg=theme.BG,
            fg=theme.TEXT_DIM,
            font=fonts["dim"],
        ).pack(anchor="w", pady=(0, 6))

        listrow = tk.Frame(body, bg=theme.BG)
        listrow.pack(fill="x")
        self._list = tk.Listbox(
            listrow, bg=theme.BG_CARD, fg=theme.TEXT, selectbackground=theme.ACCENT, height=5
        )
        self._list.pack(side="left", fill="both", expand=True)
        btns = tk.Frame(listrow, bg=theme.BG)
        btns.pack(side="left", padx=(8, 0))
        tk.Button(btns, text="Add", bg=theme.ACCENT, fg="white", command=self._add_folder).pack(
            fill="x", pady=(0, 4)
        )
        tk.Button(btns, text="Remove", bg=theme.BG_CARD, fg=theme.TEXT, command=self._remove_folder).pack(fill="x")
        for p in self.settings.get("local_folders", []):
            self._list.insert("end", p)

        tk.Label(body, text="Auto-update", bg=theme.BG, fg=theme.TEXT, font=fonts["h1"]).pack(
            anchor="w", pady=(14, 4)
        )
        row = tk.Frame(body, bg=theme.BG)
        row.pack(fill="x")
        self._auto = tk.BooleanVar(value=bool(self.settings.get("auto_update")))
        tk.Checkbutton(
            row, text="Check for updates on startup", variable=self._auto, bg=theme.BG, fg=theme.TEXT,
            selectcolor=theme.BG_CARD, activebackground=theme.BG, activeforeground=theme.TEXT,
        ).pack(side="left")
        tk.Label(
            row,
            text="Downloads new releases from the project's GitHub page and replaces the launcher when you confirm.",
            bg=theme.BG, fg=theme.TEXT_DIM, font=fonts["dim"],
        ).pack(side="left", padx=(8, 0))

        tk.Label(body, text="Steam API", bg=theme.BG, fg=theme.TEXT, font=fonts["h1"]).pack(
            anchor="w", pady=(14, 4)
        )
        tk.Label(
            body,
            text="Steam Web API key for fetching playtime. Get a free key at:",
            bg=theme.BG, fg=theme.TEXT_DIM, font=fonts["dim"],
        ).pack(anchor="w", pady=(0, 4))
        getrow = tk.Frame(body, bg=theme.BG)
        getrow.pack(fill="x", pady=(0, 4))
        tk.Button(
            getrow, text="Get my key", bg=theme.ACCENT, fg="white",
            command=self._open_key_page, cursor="hand2",
        ).pack(side="left")
        tk.Label(
            getrow,
            text="steamcommunity.com/dev/apikey\nPaste it below; it is verified live when you save.",
            bg=theme.BG, fg=theme.TEXT_DIM, font=fonts["dim"],
        ).pack(side="left", padx=(8, 0))
        sf = tk.Frame(body, bg=theme.BG)
        sf.pack(fill="x")
        self._steam_key = tk.StringVar(value=get_steam_api_key())
        tk.Entry(sf, textvariable=self._steam_key, bg=theme.BG_CARD, fg=theme.TEXT,
                 insertbackground=theme.TEXT, show="*").pack(side="left", fill="x", expand=True)

        footer = tk.Frame(body, bg=theme.BG)
        footer.pack(fill="x", pady=(16, 0))
        ver = config_data_version()
        tk.Label(footer, text=f"Insomnia Launcher {ver}", bg=theme.BG, fg=theme.TEXT_DIM, font=fonts["dim"]).pack(
            side="left"
        )
        tk.Button(footer, text="Save", bg=theme.ACCENT, fg="white", command=self._save).pack(side="right")
        tk.Button(
            footer, text="Rescan now", bg=theme.BG_CARD, fg=theme.TEXT, command=self._rescan
        ).pack(side="right", padx=6)
        self._status_label = tk.Label(body, text="", bg=theme.BG, fg=theme.TEXT, font=fonts["dim"])
        self._status_label.pack(fill="x", pady=(6, 0))

    def _open_key_page(self):
        webbrowser.open("https://steamcommunity.com/dev/apikey")

    def _finish_verify(self, key, ok, msg, persist, status):
        if self.winfo_exists() == 0:
            return
        if not ok:
            self._status_label.config(text="", fg=theme.TEXT)
            messagebox.showerror("Steam API key", f"Key rejected:\n{msg}", parent=self)
            return
        self._status_label.config(text="", fg=theme.TEXT)
        messagebox.showinfo(
            "Steam API key",
            f"Key verified ({msg}).\n\nPlaytime will be fetched on rescan.",
            parent=self,
        )
        persist()

    def _rescan(self):
        self._save(then=self.on_rescan)

    def _save(self, then=None):
        key = self._steam_key.get().strip()
        existing = get_steam_api_key()

        def persist():
            if key:
                set_steam_api_key(key)
            else:
                from app.steam_api import STEAM_API_KEY_FILE
                if os.path.isfile(STEAM_API_KEY_FILE):
                    os.unlink(STEAM_API_KEY_FILE)
            self.on_save(
                {
                    "local_folders": list(self._list.get(0, "end")),
                    "auto_update": self._auto.get(),
                }
            )
            if then:
                then()
            self.destroy()

        if key and key != existing:
            status = self._status_label
            status.config(text="Verifying key...", fg=theme.TEXT)
            self.update()

            def verify():
                from app.steam_api import check_steam_api_key
                ok, msg = check_steam_api_key(key)
                self.after(0, lambda: self._finish_verify(key, ok, msg, persist, status))

            threading.Thread(target=verify, daemon=True).start()
        else:
            persist()

    def _add_folder(self):
        path = filedialog.askdirectory(parent=self, title="Choose a folder to scan")
        if not path:
            return
        cur = set(self._list.get(0, "end"))
        if path not in cur:
            self._list.insert("end", path)

    def _remove_folder(self):
        sel = self._list.curselection()
        if sel:
            self._list.delete(sel[0])


class AddGameDialog(tk.Toplevel):
    def __init__(self, master, on_add):
        super().__init__(master)
        self.on_add = on_add
        self.title("Add game")
        self.configure(bg=theme.BG)
        self.transient(master)
        self.resizable(False, False)

        fonts = theme.load_fonts()
        tk.Label(
            self,
            text="Pick a game executable (.exe / .sh / .AppImage) or a folder.",
            bg=theme.BG, fg=theme.TEXT, font=fonts["h1"],
        ).pack(padx=16, pady=(16, 8), anchor="w")
        row = tk.Frame(self, bg=theme.BG)
        row.pack(fill="x", padx=16, pady=(0, 16))
        tk.Button(row, text="Browse file...", bg=theme.ACCENT, fg="white", command=self._file).pack(side="left")
        tk.Button(row, text="Browse folder...", bg=theme.BG_CARD, fg=theme.TEXT, command=self._folder).pack(
            side="left", padx=8
        )
        tk.Button(row, text="Cancel", bg=theme.BG_CARD, fg=theme.TEXT, command=self.destroy).pack(side="right")
        self.grab_set()

    def _file(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Choose game executable",
            filetypes=[("Executables", "*.exe *.sh *.AppImage *.run *.bin"), ("All files", "*.*")],
        )
        if path:
            self._submit(path)

    def _folder(self):
        path = filedialog.askdirectory(parent=self, title="Choose game folder")
        if path:
            self._submit(path)

    def _submit(self, path):
        game = local.pick_manual_file(path)
        if game is None:
            tk.messagebox.showwarning("No game found", "No obvious game executable found there.", parent=self)
            return
        self.destroy()
        self.on_add(game)


def config_data_version():
    try:
        from app.version import __version__
    except Exception:
        return "?"
    return __version__