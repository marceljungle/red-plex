"""Response models for upstream sync operations."""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional


@dataclass
class AlbumSyncInfo:
    """Information about an album to be synced."""
    group_id: str
    display_name: str
    artists: Optional[List[str]] = None
    album_name: Optional[str] = None


@dataclass
class CollagePreviewData:
    """Preview data for a collage to be synced."""
    collage_id: str
    collage_name: str
    external_id: str
    site: str
    albums_to_add: List[AlbumSyncInfo]


@dataclass
class UpstreamSyncPreviewResponse:
    """Response containing preview data for upstream sync."""
    preview_data: List[CollagePreviewData]
    success: bool
    error_message: Optional[str] = None


@dataclass
class UpstreamSyncResponse:
    """Response from upstream sync operation."""
    success: bool
    synced_collages: int
    total_collages: int
    errors: List[str]
    sync_results: Dict[str, Dict[str, Any]]  # collage_id -> sync results
