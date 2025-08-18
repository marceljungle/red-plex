"""Use case for showing missing torrent groups in local collections."""

from red_plex.infrastructure.db.local_database import LocalDatabase
from red_plex.infrastructure.logger.logger import logger
from red_plex.infrastructure.rest.gazelle.gazelle_api import GazelleAPI
from red_plex.use_case.show_missing.show_missing_response import (
    ShowMissingResponse, MissingGroupInfo
)


# pylint: disable=R0903
class ShowMissingUseCase:
    """Use case for finding missing torrent groups in local collections."""

    def __init__(self, db: LocalDatabase, gazelle_api: GazelleAPI):
        """Initialize the use case with required dependencies."""
        self.db = db
        self.gazelle_api = gazelle_api

    # pylint: disable=R0914
    def execute(self, collage_id: str) -> ShowMissingResponse:
        """
        Execute the show missing use case.

        Args:
            collage_id: The external ID of the collage to check

        Returns:
            ShowMissingResponse with the results
        """
        # Get the local collection by external_id
        local_collection = self.db.get_collage_collection_by_external_id(collage_id)
        if not local_collection:
            return ShowMissingResponse(
                success=False,
                collage_name="",
                site="",
                missing_groups=[],
                error_message=(
                    f"No local collection found for collage ID {collage_id}. "
                    f"You may need to convert it first using "
                    f"'red-plex collages convert {collage_id} --site <site>'"
                )
            )

        site = local_collection.site

        # Get the current collage from the site
        try:
            site_collection = self.gazelle_api.get_collage(collage_id)
        except Exception as e:  # pylint: disable=W0718
            logger.error("Failed to fetch collage from site: %s", e, exc_info=True)
            return ShowMissingResponse(
                success=False,
                collage_name=local_collection.name,
                site=site,
                missing_groups=[],
                error_message=f"Failed to fetch collage {collage_id} from {site.upper()} - {e}"
            )

        if not site_collection:
            return ShowMissingResponse(
                success=False,
                collage_name=local_collection.name,
                site=site,
                missing_groups=[],
                error_message=f"Collage {collage_id} not found on {site.upper()}"
            )

        # Compare group IDs
        local_group_ids = {int(tg.id) for tg in local_collection.torrent_groups}
        site_group_ids = {int(tg.id) for tg in site_collection.torrent_groups}
        missing_group_ids = site_group_ids - local_group_ids

        # If no missing groups, return success with empty list
        if not missing_group_ids:
            return ShowMissingResponse(
                success=True,
                collage_name=local_collection.name,
                site=site,
                missing_groups=[]
            )

        # Fetch details for each missing group
        missing_groups = []
        for group_id in sorted(missing_group_ids):
            try:
                torrent_group = self.gazelle_api.get_torrent_group(str(group_id))
                if torrent_group:
                    artists = torrent_group.artists if torrent_group.artists else ["Unknown Artist"]
                    album_name = torrent_group.album_name or "Unknown Album"
                    torrent_url = self.gazelle_api.get_torrent_group_url(str(group_id))

                    missing_groups.append(MissingGroupInfo(
                        group_id=group_id,
                        artist_names=artists,
                        album_name=album_name,
                        torrent_url=torrent_url
                    ))
                else:
                    # Group details not available, but still add basic info
                    missing_groups.append(MissingGroupInfo(
                        group_id=group_id,
                        artist_names=["Unknown Artist"],
                        album_name="Details not available",
                        torrent_url=self.gazelle_api.get_torrent_group_url(str(group_id))
                    ))
            except Exception as e:  # pylint: disable=W0718
                logger.warning("Failed to fetch details for group %s: %s", group_id, e)
                # Add basic info even if details fetch failed
                missing_groups.append(MissingGroupInfo(
                    group_id=group_id,
                    artist_names=["Unknown Artist"],
                    album_name="Error fetching details",
                    torrent_url=self.gazelle_api.get_torrent_group_url(str(group_id))
                ))

        return ShowMissingResponse(
            success=True,
            collage_name=local_collection.name,
            site=site,
            missing_groups=missing_groups
        )
