""" Domain models for the project. """

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass(frozen=True)
class Album:
    """
    Represents an album.
    """
    id: str = ""
    name: str = ""
    artists: List[str] = field(default_factory=list)
    added_at: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
    path: str = ""

    def __hash__(self) -> int:
        return hash((self.id, tuple(self.artists), self.name, self.added_at, self.path))


@dataclass(frozen=True)
class TorrentGroup:
    """
    Represents a torrent group with all related file paths, in this case,
    for each and every torrent present in the group.
    """
    id: int
    artists: List[str] = field(default_factory=list)
    album_name: str = ""
    file_paths: List[str] = field(default_factory=list)

    def __hash__(self) -> int:
        return hash((self.id, tuple(self.artists), self.album_name, tuple(self.file_paths)))


@dataclass(frozen=True)
class Collection:
    """
    Represents a collection which is going to store the list of torrent groups
    and the relation between the server and site (id <-> external_id).
    """
    id: str = ""
    external_id: str = ""
    name: str = ""
    torrent_groups: List[TorrentGroup] = field(default_factory=list)
    site: str = ""
