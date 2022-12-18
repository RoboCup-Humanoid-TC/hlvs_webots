from typing import List

from data_collection.match_info.frame import Frame


class MatchObject:
    def __init__(self, id: int, mass: float, frames: List[Frame]):
        """Initialize MatchObject.

        :param id: Unique id of the object
        :type id: int
        :param mass: Mass of the object in kg
        :type mass: float
        :param frames: List of frames that are part of the object
        :type frames: List[Frame]
        """
        self.id: int = id
        self.mass: float = mass
        self.frames: List[Frame] = frames
