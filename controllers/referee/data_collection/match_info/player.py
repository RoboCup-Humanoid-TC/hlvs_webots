from dataclasses import dataclass
from enum import Enum, unique
from typing import List

from data_collection.match_info.camera import Camera
from data_collection.match_info.frame import Frame
from data_collection.match_info.match_object import MatchObject, StaticMatchObject


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


@dataclass(frozen=True)
class StaticPlayer(StaticMatchObject):
    """Static information about a player.

    :param id: Unique id of the player object
    :type id: str
    :param mass: Mass of the player in kg
    :type mass: float
    :param cameras: List of cameras that are part of the player
    :type cameras: List[Camera]
    :param DOF: Degrees of freedom of the player
    :type DOF: int
    :param platform: Robot platform of the player
    :type platform: str
    """

    cameras: List[Camera]
    DOF: int
    platform: str

    def is_mono_camera(self) -> bool:
        """Check if the player has a mono camera.
        This is the case if the player has exactly one camera and
        the frame_id is "camera_frame".

        :return: True if the player has a mono camera, False otherwise
        :rtype: bool
        """
        return len(self.cameras) == 1 and self.cameras[0].frame_id == "camera_frame"

    def is_stereo_camera(self) -> bool:
        """Check if the player has a stereo camera.
        This is the case if the player has exactly two cameras and
        the frame_ids are "l_camera_frame" and "r_camera_frame".

        :return: True if the player has a stereo camera, False otherwise
        :rtype: bool
        """
        # Check for correct frame_ids
        our_frame_ids = set([camera.frame_id for camera in self.cameras])
        correct_frame_ids = set(["l_camera_frame", "r_camera_frame"])
        frame_ids_OK = our_frame_ids == correct_frame_ids

        return len(self.cameras) == 2 and frame_ids_OK


class Player(MatchObject):
    def __init__(
        self,
        id: str,
        frames: List[Frame],
    ) -> None:
        """Initialize Player.

        :param id: Unique id of the player object
        :type id: str
        :param frames: List of frames that are part of the player
        :type frames: List[Frame]
        """
        super().__init__(id, frames)

        self.state: State = State.UNKNOWN_STATE
        self.role: Role = Role.ROLE_UNDEFINED
        self.action: Action = Action.ACTION_UNDEFINED
