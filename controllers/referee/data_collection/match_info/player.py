from enum import Enum, unique
from typing import List
from data_collection.match_info.frame import Frame

from data_collection.match_info.camera import Camera
from data_collection.match_info.match_object import MatchObject


@unique
class State(Enum):
    """Enum for player states."""

    UNKNOWN_STATE = 0
    UNPENALISED = 1
    PENALISED = 2


@unique
class Role(Enum):
    """Enum for player roles."""

    ROLE_UNDEFINED = 0
    ROLE_IDLING = 1
    ROLE_OTHER = 2
    ROLE_STRIKER = 3
    ROLE_SUPPORTER = 4
    ROLE_DEFENDER = 5
    ROLE_GOALIE = 6


@unique
class Action(Enum):
    """Enum for the current action of the robot."""

    ACTION_UNDEFINED = 0
    ACTION_POSITIONING = 1
    ACTION_GOING_TO_BALL = 2
    ACTION_TRYING_TO_SCORE = 3
    ACTION_WAITING = 4
    ACTION_KICKING = 5
    ACTION_SEARCHING = 6
    ACTION_LOCALIZING = 7


class Player(MatchObject):
    def __init__(
        self,
        id: int,
        mass: float,
        frames: List[Frame],
        cameras: List[Camera],
        DOF: int,
        platform: str,
    ) -> None:
        """Initialize Player.

        :param id: Unique id of the player object
        :type id: int
        :param mass: Mass of the player in kg
        :type mass: float
        :param frames: List of frames that are part of the player
        :type frames: List[Frame]
        :param cameras: List of cameras that are part of the player
        :type cameras: List[Camera]
        :param DOF: Degrees of freedom of the player
        :type DOF: int
        :param platform: Robot platform of the player
        :type platform: str
        """
        super().__init__(id, mass, frames)
        self.cameras: List[Camera] = cameras
        self.DOF: int = DOF
        self.platform: str = platform

        self.state: State = State.UNKNOWN_STATE
        self.role: Role = Role.ROLE_UNDEFINED
        self.action: Action = Action.ACTION_UNDEFINED
