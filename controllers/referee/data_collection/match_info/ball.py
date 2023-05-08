from dataclasses import dataclass

from dataclasses_json import DataClassJsonMixin

from .frame import Frame
from .match_object import MatchObject, StaticMatchObject


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


@dataclass
class Ball(MatchObject, DataClassJsonMixin):
    """Ball object.

    :param id: Unique id of the ball object
    :type id: str
    :param frame: Frame that are part of the ball object
    :type frame: Frame
    """

    frame: Frame
