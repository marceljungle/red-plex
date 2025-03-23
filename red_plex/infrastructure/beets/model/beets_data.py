"""Basic beets data model."""


# pylint: disable=too-few-public-methods
class BeetsData:
    """Beets data model."""
    def __init__(self, source_destination: dict) -> None:
        self.source_destination = source_destination
