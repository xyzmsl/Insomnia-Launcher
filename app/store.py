import os
import sqlite3
import time
from contextlib import contextmanager

from app.config import DB_PATH


class Store:
    def __init__(self, path=DB_PATH):
        self.path = path
        parent = os.path.dirname(self.path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()

    def _init_schema(self):
        with self._conn:
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS games (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    launch_target TEXT NOT NULL,
                    exe TEXT DEFAULT '',
                    install_dir TEXT DEFAULT '',
                    cover_url TEXT DEFAULT '',
                    cover_path TEXT DEFAULT '',
                    platform TEXT DEFAULT '',
                    manual INTEGER DEFAULT 0,
                    favorite INTEGER DEFAULT 0,
                    hidden INTEGER DEFAULT 0,
                    last_seen INTEGER DEFAULT 0,
                    genre TEXT DEFAULT '',
                    playtime INTEGER DEFAULT 0,
                    last_played INTEGER DEFAULT 0
                )
                """
            )
            for col, default in [("genre", "''"), ("playtime", "0"), ("last_played", "0")]:
                try:
                    self._conn.execute(f"SELECT {col} FROM games LIMIT 1")
                except sqlite3.OperationalError:
                    coltype = "TEXT" if col == "genre" else "INTEGER"
                    self._conn.execute(f"ALTER TABLE games ADD COLUMN {col} {coltype} DEFAULT {default}")
            self._ensure_int_columns()
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT NOT NULL,
                    start INTEGER NOT NULL,
                    end INTEGER,
                    seconds INTEGER DEFAULT 0,
                    tracked INTEGER DEFAULT 0
                )
                """
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
                """
            )

    def _ensure_int_columns(self):
        try:
            cols = {
                r["name"]: r["type"].upper() for r in self._conn.execute("PRAGMA table_info(games)")
            }
        except sqlite3.OperationalError:
            return
        needs = [c for c in ("playtime", "last_played") if cols.get(c) != "INTEGER"]
        if not needs:
            return
        with self._conn:
            self._conn.execute("DROP TABLE IF EXISTS games_migrate")
            self._conn.execute(
                """
                CREATE TABLE games_migrate (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    launch_target TEXT NOT NULL,
                    exe TEXT DEFAULT '',
                    install_dir TEXT DEFAULT '',
                    cover_url TEXT DEFAULT '',
                    cover_path TEXT DEFAULT '',
                    platform TEXT DEFAULT '',
                    manual INTEGER DEFAULT 0,
                    favorite INTEGER DEFAULT 0,
                    hidden INTEGER DEFAULT 0,
                    last_seen INTEGER DEFAULT 0,
                    genre TEXT DEFAULT '',
                    playtime INTEGER DEFAULT 0,
                    last_played INTEGER DEFAULT 0
                )
                """
            )
            self._conn.execute(
                """
                INSERT INTO games_migrate (id, name, source, launch_target, exe, install_dir,
                                           cover_url, cover_path, platform, manual, favorite, hidden,
                                           last_seen, genre, playtime, last_played)
                SELECT id, name, source, launch_target, exe, install_dir,
                       cover_url, cover_path, platform, manual, favorite, hidden,
                       last_seen, genre,
                       COALESCE(CAST(playtime AS INTEGER), 0),
                       COALESCE(CAST(last_played AS INTEGER), 0)
                FROM games
                """
            )
            self._conn.execute("DROP TABLE games")
            self._conn.execute("ALTER TABLE games_migrate RENAME TO games")

    @contextmanager
    def cursor(self):
        cur = self._conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def upsert_games(self, games, prune_missing=True):
        now = int(time.time())
        ids = set()
        with self._conn:
            for g in games:
                row = g.to_row()
                self._conn.execute(
                    """
                    INSERT INTO games (id, name, source, launch_target, exe, install_dir,
                                       cover_url, cover_path, platform, manual, last_seen, genre,
                                       playtime, last_played)
                    VALUES (:id, :name, :source, :launch_target, :exe, :install_dir,
                            :cover_url, :cover_path, :platform, :manual, :last_seen, :genre,
                            :playtime, :last_played)
                    ON CONFLICT(id) DO UPDATE SET
                        name=excluded.name, source=excluded.source,
                        launch_target=excluded.launch_target, exe=excluded.exe,
                        install_dir=excluded.install_dir, cover_url=excluded.cover_url,
                        cover_path=excluded.cover_path, platform=excluded.platform,
                        manual=excluded.manual, last_seen=excluded.last_seen,
                        genre=CASE WHEN excluded.genre != '' THEN excluded.genre ELSE games.genre END,
                        playtime=CASE WHEN excluded.playtime > 0 THEN excluded.playtime ELSE games.playtime END,
                        last_played=CASE WHEN excluded.last_played > 0 THEN excluded.last_played ELSE games.last_played END,
                        hidden=games.hidden
                    """,
                    {**row, "last_seen": now},
                )
                ids.add(row["id"])
        if prune_missing:
            with self._conn:
                self._conn.execute(
                    "DELETE FROM games WHERE manual=0 AND hidden=0 AND last_seen < ?",
                    (now,),
                )

    def add_manual(self, game):
        row = game.to_row()
        row["manual"] = 1
        with self._conn:
            self._conn.execute(
                """
                INSERT INTO games (id, name, source, launch_target, exe, install_dir,
                                   cover_url, cover_path, platform, manual, last_seen)
                VALUES (:id, :name, :source, :launch_target, :exe, :install_dir,
                        :cover_url, :cover_path, :platform, :manual, :last)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name, exe=excluded.exe,
                    install_dir=excluded.install_dir, hidden=0
                """,
                {**row, "last": int(time.time())},
            )

    def all_games(self, include_hidden=False):
        sql = "SELECT * FROM games"
        if not include_hidden:
            sql += " WHERE hidden=0"
        with self.cursor() as cur:
            cur.execute(sql + " ORDER BY name COLLATE NOCASE")
            return [dict(r) for r in cur.fetchall()]

    def get(self, game_id):
        with self.cursor() as cur:
            cur.execute("SELECT * FROM games WHERE id=?", (game_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def set_favorite(self, game_id, value):
        with self._conn:
            self._conn.execute("UPDATE games SET favorite=? WHERE id=?", (1 if value else 0, game_id))

    def set_hidden(self, game_id, value):
        with self._conn:
            self._conn.execute("UPDATE games SET hidden=? WHERE id=?", (1 if value else 0, game_id))

    def set_genre(self, game_id, genre):
        with self._conn:
            self._conn.execute("UPDATE games SET genre=? WHERE id=?", (genre, game_id))

    def all_genres(self):
        with self.cursor() as cur:
            cur.execute("SELECT DISTINCT genre FROM games WHERE genre != '' AND hidden=0 ORDER BY genre")
            return [r["genre"] for r in cur.fetchall()]

    def update_cover(self, game_id, cover_path):
        with self._conn:
            self._conn.execute("UPDATE games SET cover_path=? WHERE id=?", (cover_path, game_id))

    def track_sources(self):
        with self.cursor() as cur:
            cur.execute("SELECT DISTINCT source FROM games WHERE hidden=0")
            return [r["source"] for r in cur.fetchall()]

    def start_session(self, game_id):
        now = int(time.time())
        with self._conn:
            cur = self._conn.execute(
                "INSERT INTO sessions (game_id, start, tracked) VALUES (?, ?, 1)",
                (game_id, now),
            )
            return cur.lastrowid

    def _close_session(self, session_id, end, seconds, tracked):
        with self._conn:
            self._conn.execute(
                "UPDATE sessions SET end=?, seconds=?, tracked=? WHERE id=?",
                (end, seconds, 1 if tracked else 0, session_id),
            )
            self._conn.execute(
                "UPDATE games SET last_seen=? WHERE id=(SELECT game_id FROM sessions WHERE id=?)",
                (end, session_id),
            )

    def close_session(self, session_id, tracked=True):
        end = int(time.time())
        with self.cursor() as cur:
            cur.execute("SELECT start FROM sessions WHERE id=?", (session_id,))
            row = cur.fetchone()
            if not row:
                return
            seconds = max(0, end - row["start"])
        self._close_session(session_id, end, seconds, tracked)

    def close_all_open_sessions(self):
        with self.cursor() as cur:
            cur.execute("SELECT id FROM sessions WHERE end IS NULL")
            ids = [r["id"] for r in cur.fetchall()]
        for sid in ids:
            self.close_session(sid, tracked=False)

    def total_playtime(self, game_id):
        with self.cursor() as cur:
            cur.execute("SELECT source FROM games WHERE id=?", (game_id,))
            row = cur.fetchone()
            source = row["source"] if row else ""
            cur.execute("SELECT SUM(seconds) AS t FROM sessions WHERE game_id=?", (game_id,))
            row = cur.fetchone()
            local = row["t"] or 0
            cur.execute("SELECT playtime FROM games WHERE id=?", (game_id,))
            row = cur.fetchone()
            api = 0
            if row and row["playtime"]:
                try:
                    api = int(row["playtime"])
                except (ValueError, TypeError):
                    pass
            if source == "steam":
                return max(local, api)
            return api + local

    def last_played(self, game_id):
        with self.cursor() as cur:
            cur.execute(
                "SELECT MAX(start) AS t FROM sessions WHERE game_id=? AND seconds > 0",
                (game_id,),
            )
            row = cur.fetchone()
            local = row["t"] or 0
            cur.execute("SELECT last_played FROM games WHERE id=?", (game_id,))
            row = cur.fetchone()
            api = 0
            if row and row["last_played"]:
                try:
                    api = int(row["last_played"])
                except (ValueError, TypeError):
                    pass
            return max(local, api)

    def is_favorite(self, game_id):
        row = self.get(game_id)
        return bool(row and row.get("favorite"))

    def touch(self, game_id):
        now = int(time.time())
        with self._conn:
            self._conn.execute(
                "UPDATE games SET last_seen=? WHERE id=? AND last_seen < ?",
                (now, game_id, now),
            )

    def stats(self, game_id):
        return {
            "playtime": self.total_playtime(game_id),
            "last_played": self.last_played(game_id),
        }

    def playtime_map(self):
        out = {}
        api_map = {}
        with self.cursor() as cur:
            cur.execute("SELECT id, playtime, source FROM games WHERE playtime > 0")
            for r in cur.fetchall():
                try:
                    api_map[r["id"]] = (int(r["playtime"]), r["source"] or "")
                except (ValueError, TypeError):
                    pass
            cur.execute(
                "SELECT game_id, SUM(seconds) AS t FROM sessions WHERE seconds > 0 GROUP BY game_id"
            )
            for r in cur.fetchall():
                gid = r["game_id"]
                local = r["t"] or 0
                api, source = api_map.get(gid, (0, ""))
                if source == "steam":
                    out[gid] = max(api, local)
                else:
                    out[gid] = api + local
            for gid, (api, source) in api_map.items():
                if gid not in out:
                    out[gid] = api
        return out

    def last_played_map(self):
        out = {}
        with self.cursor() as cur:
            cur.execute("SELECT id, last_played FROM games WHERE last_played > 0")
            for r in cur.fetchall():
                try:
                    out[r["id"]] = int(r["last_played"])
                except (ValueError, TypeError):
                    pass
            cur.execute(
                "SELECT game_id, MAX(start) AS t FROM sessions WHERE seconds > 0 GROUP BY game_id"
            )
            for r in cur.fetchall():
                gid = r["game_id"]
                val = r["t"] or 0
                if val > out.get(gid, 0):
                    out[gid] = val
        return out