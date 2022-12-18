from typing import List
from data_collection.match_info.frame import Frame
from data_collection.match_info.match_object import MatchObject


class Ball(MatchObject):
    def __init__(
        self, id: int, mass: float, frames: List[Frame], texture: str, diameter: float
    ) -> None:
        """Initialize Ball.

        :param id: Unique id of the object
        :type id: int
        :param mass: Mass of the object in kg
        :type mass: float
        :param frames: List of frames that are part of the object
        :type frames: List[Frame]
        :param texture: Texture of the ball
        :type texture: str
        :param diameter: Diameter of the ball in mm
        :type diameter: float
        """
        super().__init__(id, mass, frames)
        self.texture: str = texture
        self.diameter: float = diameter
