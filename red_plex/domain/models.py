""" Domain models for the project. """

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class Album:
    """
    Represents an album.
    """
    id: str = ""
    added_at: datetime = datetime(1970, 1, 1, tzinfo=timezone.utc)
    path: str = ""


@dataclass
class TorrentGroup:
    """
    Represents a torrent group with all related file paths, in this case,
    for each and every torrent present in the group.
    """
    id: int
    file_paths: List[str] = field(default_factory=list)


@dataclass
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
