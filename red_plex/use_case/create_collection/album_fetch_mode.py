""" Album fetch mode enum """
from enum import Enum


class AlbumFetchMode(Enum):
    """ Album fetch mode enum with the different fetching possibilities. """
    NORMAL = 1
    EXTERNAL = 2
    MIXED = 3
