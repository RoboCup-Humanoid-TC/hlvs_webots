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

    def set_state(self, state: State) -> None:
        """Set the state of the player.

        :param state: State of the player
        :type state: State
        """
        self.state = state

    def set_role(self, role: Role) -> None:
        """Set the role of the player.

        :param role: Role of the player
        :type role: Role
        """
        self.role = role

    def set_action(self, action: Action) -> None:
        """Set the action of the player.

        :param action: Action of the player
        :type action: Action
        """
        self.action = action

    def get_frame(self, frame_id: str) -> Frame:
        """Returns the frame with the given id.

        :param frame_id: Id of the frame
        :type frame_id: str
        :raises ValueError: If no frame with the given id exists
        :return: Frame with the given id
        :rtype: Frame
        """
        for frame in self.frames:
            if frame.id == frame_id:
                return frame
        raise ValueError(f"Frame with id {frame_id} not found")

    def get_base_link(self) -> Frame:
        """Returns the base link frame of the player.

        :raises ValueError: If no base link frame exists
        :return: Base link frame of the player
        :rtype: Frame
        """
        return self.get_frame("base_link")

    def get_l_sole(self) -> Frame:
        """Returns the left sole frame of the player.

        :raises ValueError: If no left sole frame exists
        :return: Left sole frame of the player
        :rtype: Frame
        """
        return self.get_frame("l_sole")

    def get_r_sole(self) -> Frame:
        """Returns the right sole frame of the player.

        :raises ValueError: If no right sole frame exists
        :return: Right sole frame of the player
        :rtype: Frame
        """
        return self.get_frame("r_sole")

    def get_soles(self) -> List[Frame]:
        """Returns the left and right sole frames of the player.

        :raises ValueError: If no left or right sole frame exists
        :return: Left and right sole frames of the player
        :rtype: List[Frame]
        """
        return [self.get_l_sole(), self.get_r_sole()]

    def get_l_gripper(self) -> Frame:
        """Returns the left gripper frame of the player.

        :raises ValueError: If no left gripper frame exists
        :return: Left gripper frame of the player
        :rtype: Frame
        """
        return self.get_frame("l_gripper")

    def get_r_gripper(self) -> Frame:
        """Returns the right gripper frame of the player.

        :raises ValueError: If no right gripper frame exists
        :return: Right gripper frame of the player
        :rtype: Frame
        """
        return self.get_frame("r_gripper")

    def get_grippers(self) -> List[Frame]:
        """Returns the left and right gripper frames of the player.

        :raises ValueError: If no left or right gripper frame exists
        :return: Left and right gripper frames of the player
        :rtype: List[Frame]
        """
        return [self.get_l_gripper(), self.get_r_gripper()]

    def get_camera_frame(self) -> Frame:
        """Returns the camera frame of the player.

        :raises ValueError: If no camera frame exists
        :return: Camera frame of the player
        :rtype: Frame
        """
        return self.get_frame("camera_frame")

    def get_l_camera_frame(self) -> Frame:
        """Returns the left camera frame of the player.

        :raises ValueError: If no left camera frame exists
        :return: Left camera frame of the player
        :rtype: Frame
        """
        return self.get_frame("l_camera_frame")

    def get_r_camera_frame(self) -> Frame:
        """Returns the right camera frame of the player.

        :raises ValueError: If no right camera frame exists
        :return: Right camera frame of the player
        :rtype: Frame
        """
        return self.get_frame("r_camera_frame")

    def get_camera_frames(self) -> List[Frame]:
        """Returns the left and right camera frames of the player.

        :raises ValueError: If no left or right camera frame exists
        :return: Left and right camera frames of the player
        :rtype: List[Frame]
        """
        return [self.get_l_camera_frame(), self.get_r_camera_frame()]
