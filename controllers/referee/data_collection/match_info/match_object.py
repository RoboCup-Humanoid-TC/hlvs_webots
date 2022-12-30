from dataclasses import dataclass
from typing import List

from data_collection.match_info.frame import Frame


@dataclass(frozen=True)
class StaticMatchObject:
    """Static information about a match object.

    :param id: Unique id of the object
    :type id: str
    :param mass: Mass of the object in kg
    :type mass: float
    """

    id: str
    mass: float


class MatchObject:
    def __init__(self, id: str, frames: List[Frame]):
        """Initialize MatchObject.

        :param id: Unique id of the object
        :type id: str
        :param frames: List of frames that are part of the object
        :type frames: List[Frame]
        """
        self.id: str = id
        self.frames: List[Frame] = frames
