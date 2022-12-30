from dataclasses import dataclass
from typing import List

from data_collection.match_info.frame import Frame
from data_collection.match_info.match_object import MatchObject, StaticMatchObject


@dataclass(frozen=True)
class StaticBall(StaticMatchObject):
    """Static information about a ball.

    :param id: Unique id of the ball object
    :type id: str
    :param mass: Mass of the ball in kg
    :type mass: float
    :param texture: Texture of the ball
    :type texture: str
    :param diameter: Diameter of the ball in meters
    :type diameter: float
    """

    texture: str
    diameter: float


class Ball(MatchObject):
    def __init__(self, id: str, frames: List[Frame]) -> None:
        """Initialize Ball.

        :param id: Unique id of the object
        :type id: str
        :param frames: List of frames that are part of the object
        :type frames: List[Frame]
        """
        super().__init__(id, frames)
