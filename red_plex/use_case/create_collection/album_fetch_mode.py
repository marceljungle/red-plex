""" Album fetch mode enum """
from enum import Enum


class AlbumFetchMode(Enum):
    """ Album fetch mode enum with the different fetching possibilities. """
    TORRENT_NAME = 1
    QUERY = 2
