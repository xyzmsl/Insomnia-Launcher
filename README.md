# Insomnia Launcher

A lightweight desktop game launcher that unifies your Steam, Epic, GOG, Flatpak
and locally-installed games into one clean library — with live playtime
tracking, a per-client genre artwork style, favourite pins and automatic
self-updates from this GitHub repo.

For Steam playtime, it queries Valve's Steam Web API with your own free API key —
**the key never leaves your machine** (stored only in your local settings).

---

## Screens in one line

- **Library** — grid of cover-art cards for every detected game.
- **Favourites / Recent** — filter views pinned in the sidebar.
- **Search + filters** — quick text search, per-source and per-genre filtering
  (Steam / Epic / GOG / Local / Flatpak) and a sort key (name / recent / playtime).
- **Details panel** — cover, launch, play button, favourite star, playtime,
  last-played, and a "hide from library" option for stuff you never launch.
- **Right-click context menu** per game for the fast actions.
- **Settings** — Steam API key, genre colours, scan folders, auto-update toggle.

---

## Install

### Linux

1. Build the launcher once:

   ```bash
   ./packaging/build_linux.sh
   ```

   This produces a single-file `dist/InsomniaLauncher` binary
   (PyInstaller, windowed, no external runtime needed).

2. Install it to your user's home tree (no `sudo` needed) and register the app:

   ```bash
   ./packaging/install_linux.sh            # user install: ~/.local/bin + ~/.local/share
   # or for all users on the machine:
   sudo ./packaging/install_linux.sh system
   ```

   This copies the binary to `~/.local/bin` and a `.desktop` entry + icon to
   `~/.local/share/applications` / `~/.local/share/icons`, so the launcher
   appears in the start menu. `~/.local/bin` must be on your `PATH` (add
   `export PATH="$HOME/.local/bin:$PATH"` to `~/.bashrc`/`~/.profile` if it
   isn't).

   Your library, Steam API key and settings live in
   `~/.local/share/insomnia-launcher` and are **never touched** by
   re-installs or updates.

### Windows

1. Build the exe once:

   ```bat
   packaging\build_windows.bat
   ```

2. Build the installer (requires [Inno Setup 6](https://jrsoftware.org/isinfo.php),
   `iscc` in your PATH):

   ```bat
   packaging\build_windows_installer.bat
   ```

   This produces `dist\InsomniaLauncherSetup.exe`. Run it, pick Install, and the
   launcher is registered in your Start menu with an optional desktop shortcut.
   No admin rights required — everything installs under `%LOCALAPPDATA%`.
   Settings, your Steam API key and library DB live under
   `%LOCALAPPDATA%\Insomnia Launcher\data` and survive upgrades; uninstalling
   the launcher leaves your installed games untouched.

---

## Steam API key — step by step (needed only for playtime)

Playtime is fetched from the **Steam Web API** using *your own* free key.
Steam never hands out playtime without per-account authentication, so a key is
required. Here's the whole flow:

1. Go to <https://steamcommunity.com/dev/apikey> while logged into your Steam
   account.
2. Accept the "Subscriber Agreement".
3. In the "Domain name" box you can type anything (e.g. `localhost`) — the
   launcher fetches your *own* playtime, not a third-party site's.
4. Click **Register**. Copy the 32-character key shown.
5. Open **Settings → Steam API** in the launcher, paste the key and Save.

The launcher only reads **your** profile's playtime for the games it detects,
because the data comes from your own key. Your key is stored **locally only**
in `~/.local/share/insomnia-launcher/settings.json` (Linux) or
`%LOCALAPPDATA%\Insomnia Launcher\data\settings.json` (Windows). It is never
uploaded anywhere.

> **Why not hardcode a shared key?** A shared key would be rate-limited across
> all users and, more importantly, would break Steam's terms for library
> browsing. A per-user key is private, uncapped for your usage, and free.

**Playtime tips**

- Playtime is refreshed on each library scan and while a game runs; totals
  accumulate in your local DB so they survive app restarts.
- If a game's playtime isn't showing, make sure (a) the key is saved, (b) the
  game is detected by a Steam install folder, and (c) you've scanned at least
  once after saving the key.
- Playtime is **read-only** — the launcher never reports playtime back to Steam
  or anywhere else.

---

## Auto-update

When **Settings → Auto-update** is enabled, the launcher checks this GitHub
repo on startup for a newer tagged release. If one exists you get a "New version
available — Download now / Later" prompt. **Download now** fetches the new
build, replaces the launcher's files and relaunches itself — without touching
your settings, Steam key or library. **Later** defers to the next startup.

Any confirmation happens with a clear dialog so you're never replaced without
consent. Auto-update is off by default (opt-in).

---

## Building from source / layout

```
main.py               Entry point
version.py            Version + app name
app/
  config.py           App/settings defaults, data-dir resolution (GitHub repo,
                      per-install config lives here)
  store.py            SQLite-backed game library + streams
  scraper.py          fetch cover art
  updater.py          GitHub release check + self-update install/relaunch
  launch.py           spawn + track games
  metrics.py          playtime/launch history
  steam_api.py        Steam Web API client (key + playtime)
ui/
  app_window.py       Main window (library, cards, filters, update prompt)
  cards.py            cover-art card widget
  dialogs.py          Settings / add-game dialogs
  theme.py            Colour palette
packaging/            Build scripts (Linux/Windows) + Inno installer
```

Requirements: Python 3.10+ with the packages in `requirements.txt`
(flask/requests/Pillow tied to the deps file — see `requirements.txt`).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py          # run from source
```

---

## FAQ

**Is any game data uploaded?** No. Only the app talks to GitHub for update
checks (version + asset download when you confirm) and to the Steam API with
*your* key for playtime. Everything else is local.

**Does uninstalling delete my games?** No — the launcher only ever stores
metadata and playtime; the game folders are scanned read-only.

**Can I hide my Steam API key?** It's stored in your settings file
(plaintext, local). It's private to you; if you'd rather not keep it, unset it
in Settings and playtime simply won't load until you re-add it.

---

## License

MIT — see [LICENSE](LICENSE).
