from dataclasses import dataclass
from enum import IntEnum, unique
from typing import Optional, Tuple

from dataclasses_json import DataClassJsonMixin

from .camera import Camera
from .frame import Frame
from .match_object import MatchObject, StaticMatchObject


@unique
class State(IntEnum):
    """Enum for player states."""

    UNKNOWN_STATE = 0
    UNPENALISED = 1
    PENALISED = 2


@unique
class Role(IntEnum):
    """Enum for player roles."""

    ROLE_UNDEFINED = 0
    ROLE_IDLING = 1
    ROLE_OTHER = 2
    ROLE_STRIKER = 3
    ROLE_SUPPORTER = 4
    ROLE_DEFENDER = 5
    ROLE_GOALIE = 6


@unique
class Action(IntEnum):
    """Enum for the current action of the robot."""

    ACTION_UNDEFINED = 0
    ACTION_POSITIONING = 1
    ACTION_GOING_TO_BALL = 2
    ACTION_TRYING_TO_SCORE = 3
    ACTION_WAITING = 4
    ACTION_KICKING = 5
    ACTION_SEARCHING = 6
    ACTION_LOCALIZING = 7


@dataclass
class RobotInfo:  # Inferred from the GameState struct
    @unique
    class Penalty(IntEnum):
        """Enum for the penalty of the robot.
        Inferred from: https://github.com/RoboCup-Humanoid-TC/GameController/blob/master/src/data/values/Penalties.java
        """

    UNKNOWN = 255
    NONE = 0
    SUBSTITUTE = 14
    MANUAL = 15
    HL_BALL_MANIPULATION = 30
    HL_PHYSICAL_CONTACT = 31
    HL_PICKUP_OR_INCAPABLE = 34
    HL_SERVICE = 35

    penalty: Penalty
    secs_till_unpenalized: int
    number_of_warnings: int
    number_of_yellow_cards: int
    number_of_red_cards: int
    goalkeeper: bool


@dataclass(frozen=True)
class StaticPlayer(StaticMatchObject):
    """Static information about a player.

    :param id: Unique id of the player object
    :type id: str
    :param mass: Mass of the player in kg
    :type mass: float
    :param DOF: Degrees of freedom of the player
    :type DOF: int
    :param platform: Robot platform of the player
    :type platform: str
    :param mono_camera: Mono camera of the player
    :type mono_camera: Optional[Camera]
    :param stereo_camera_l: Left stereo camera of the player
    :type stereo_camera_l: Optional[Camera]
    :param stereo_camera_r: Right stereo camera of the player
    :type stereo_camera_r: Optional[Camera]
    """

    DOF: int
    platform: str

    mono_camera: Optional[Camera] = None
    stereo_camera_l: Optional[Camera] = None
    stereo_camera_r: Optional[Camera] = None


@dataclass
class Player(MatchObject, DataClassJsonMixin):
    """Player is a MatchObject.

    :param id: Unique id of the player object
    :type id: str
    :param base_link: Base link frame of the player
    :type base_link: Frame
    :param l_sole: Left sole frame of the player
    :type l_sole: Frame
    :param r_sole: Right sole frame of the player
    :type r_sole: Frame
    :param l_gripper: Left gripper frame of the player
    :type l_gripper: Frame
    :param r_gripper: Right gripper frame of the player
    :type r_gripper: Frame
    :param camera_frame: Camera frame of the player
    :type camera_frame: Optional[Frame]
    :param l_camera_frame: Left camera frame of the player
    :type l_camera_frame: Optional[Frame]
    :param r_camera_frame: Right camera frame of the player
    :type r_camera_frame: Optional[Frame]
    :param state: Current state of the player, defaults to State.UNKNOWN_STATE
    :type state: State, optional
    :param role: Current role of the player, defaults to Role.ROLE_UNDEFINED
    :type role: Role, optional
    :param action: Current action of the player, defaults to Action.ACTION_UNDEFINED
    :type action: Action, optional
    :param robot_info: Robot info of the player, defaults to None
    :type robot_info: Optional[RobotInfo], optional
    """

    base_link: Frame
    l_sole: Frame
    r_sole: Frame
    l_gripper: Frame
    r_gripper: Frame

    camera_frame: Optional[Frame] = None
    l_camera_frame: Optional[Frame] = None
    r_camera_frame: Optional[Frame] = None

    state: State = State.UNKNOWN_STATE
    role: Role = Role.ROLE_UNDEFINED
    action: Action = Action.ACTION_UNDEFINED

    robot_info: Optional[RobotInfo] = None

    def get_soles(self) -> Tuple[Frame, Frame]:
        """Returns the left and right sole frames of the player.

        :return: Left and right sole frames of the player
        :rtype: Tuple[Frame, Frame]
        """
        return (self.l_sole, self.r_sole)

    def get_grippers(self) -> Tuple[Frame, Frame]:
        """Returns the left and right gripper frames of the player.

        :return: Left and right gripper frames of the player
        :rtype: Tuple[Frame, Frame]
        """
        return (self.l_gripper, self.r_gripper)

    def get_stereo_camera_frames(self) -> Tuple[Optional[Frame], Optional[Frame]]:
        """Returns the left and right camera frames of the player.

        :return: Left and right camera frames of the player
        :rtype: Tuple[Optional[Frame], Optional[Frame]]
        """
        return (self.l_camera_frame, self.r_camera_frame)
