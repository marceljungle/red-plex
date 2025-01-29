
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional

@dataclass
class TorrentGroup:
    id: int
    file_paths: List[str] = field(default_factory=list)

@dataclass
class Collage:
    id: str
    name: str = ""
    torrent_groups: List[TorrentGroup] = field(default_factory=list)

@dataclass
class Bookmarks:
    name: str
    torrent_groups: List[TorrentGroup] = field(default_factory=list)

@dataclass
class Collection:
    name: str
    rating_key: str = ""
    site: str = ""
    collage: Collage = None
    torrent_groups: List[TorrentGroup] = field(default_factory=list)