
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

@dataclass
class Album:
    id: str = ""
    added_at: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
    path: str = ""

@dataclass
class TorrentGroup:
    id: int
    file_paths: List[str] = field(default_factory=list)

@dataclass
class Collection:
    id: str = ""
    external_id: str = ""
    name: str = ""
    torrent_groups: List[TorrentGroup] = field(default_factory=list)
    site: str = ""