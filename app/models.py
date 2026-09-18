from dataclasses import dataclass
import hashlib


@dataclass
class Game:
    name: str
    source: str
    launch_target: str
    exe: str = ""
    install_dir: str = ""
    cover_url: str = ""
    cover_path: str = ""
    platform: str = ""
    manual: bool = False
    appid: str = ""
    genre: str = ""
    playtime: int = 0
    last_played: int = 0

    def game_id(self):
        raw = f"{self.source}|{self.launch_target or self.exe}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]

    def to_row(self):
        return {
            "id": self.game_id(),
            "name": self.name,
            "source": self.source,
            "launch_target": self.launch_target,
            "exe": self.exe,
            "install_dir": self.install_dir,
            "cover_url": self.cover_url,
            "cover_path": self.cover_path,
            "platform": self.platform,
            "manual": 1 if self.manual else 0,
            "genre": self.genre,
            "playtime": self.playtime,
            "last_played": self.last_played,
        }

    @classmethod
    def from_row(cls, row):
        return cls(
            name=row["name"],
            source=row["source"],
            launch_target=row["launch_target"],
            exe=row["exe"] or "",
            install_dir=row["install_dir"] or "",
            cover_url=row["cover_url"] or "",
            cover_path=row["cover_path"] or "",
            platform=row["platform"] or "",
            manual=bool(row.get("manual", 0)),
            genre=row.get("genre") or "",
            playtime=int(row.get("playtime") or 0),
            last_played=int(row.get("last_played") or 0),
        )