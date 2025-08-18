"""Response model for show missing use case."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class MissingGroupInfo:
    """Information about a missing torrent group."""
    group_id: int
    artist_names: List[str]
    album_name: str
    torrent_url: str


@dataclass
class ShowMissingResponse:
    """Response from the show missing use case."""
    success: bool
    collage_name: str
    site: str
    missing_groups: List[MissingGroupInfo]
    error_message: Optional[str] = None

    @property
    def has_missing_groups(self) -> bool:
        """Check if there are any missing groups."""
        return len(self.missing_groups) > 0
