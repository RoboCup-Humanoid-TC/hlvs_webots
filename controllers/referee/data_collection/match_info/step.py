from dataclasses import dataclass
from enum import IntEnum, unique
from typing import Optional

from dataclasses_json import DataClassJsonMixin
from forceful_contact_matrix import ForcefulContactMatrix

from .ball import Ball
from .team import Teams


@dataclass
class GameControlData:
    """Holds data of game controler communication.
    See here for more information: https://github.com/RoboCup-Humanoid-TC/GameController/wiki/GameControlData

    :param game_state: Game state
    :type game_state: GameState
    :param first_half: True if first half, False if second half
    :type first_half: bool
    :param kickoff_team: The team number of the next team to kick off or DROPBALL
    :type kickoff_team: int
    :param secondary_state: Secondary game state
    :type secondary_state: SecondaryGameState
    :param secondary_state_info_team: The team number of the team performing the secondary state (e.g. direct free kick)
    :type secondary_state_info_team: int
    :param secondary_state_info_sub_state: The sub state of the secondary state (0 for ready, 1 for freeze/ball repositioning by referee)
    :type secondary_state_info_sub_state: int
    :param drop_in_team: The team number of the team that caused last drop in
    :type drop_in_team: int
    :param drop_in_time: The number of seconds passed since the last drop in. -1 before first drop in
    :type drop_in_time: int
    :param secs_remaining: The number of seconds remaining in the half
    :type secs_remaining: int
    :param secondary_seconds_remaining: The number of seconds shown as secondary time (remaining ready, until free ball, etc)
    :type secondary_seconds_remaining: int
    """

    @unique
    class GameState(IntEnum):
        """Enum for game states.
        Inferred from the GameState struct
        """

        STATE_INITIAL = 0
        STATE_READY = 1  # Go to start position
        STATE_SET = 2  # Keep ready
        STATE_PLAYING = 3  # Start play
        STATE_FINISHED = 4  # Game over

    @unique
    class SecondaryGameState(IntEnum):
        """Enum for secondary game states.
        Inferred from the GameState struct
        """

        STATE_NORMAL = 0
        STATE_PENALTYSHOOT = 1
        STATE_OVERTIME = 2
        STATE_TIMEOUT = 3
        STATE_DIRECT_FREEKICK = 4
        STATE_INDIRECT_FREEKICK = 5
        STATE_PENALTYKICK = 6
        STATE_CORNERKICK = 7
        STATE_GOALKICK = 8
        STATE_THROWIN = 9
        STATE_DROPBALL = 128
        STATE_UNKNOWN = 255

    game_state: GameState
    first_half: bool
    kickoff_team: int
    secondary_state: SecondaryGameState
    secondary_state_info_team: int
    secondary_state_info_sub_state: int
    drop_in_team: bool  # TODO: GameState says this is bool, but docs say int
    drop_in_time: int
    seconds_remaining: int
    secondary_seconds_remaining: int


@dataclass
class Step(DataClassJsonMixin):
    """Holds data about a step.

    :param time: Time of step in simulation in seconds
    :type time: float
    :param delta_real_time: Time to calculate step in realtime in seconds, defaults to None
    :type delta_real_time: Optional[float], optional
    :param game_control_data: Game controler data, defaults to None
    :type game_control_data: Optional[GameControlData], optional
    :param ball: Ball data, defaults to None
    :type ball: Optional[Ball], optional
    :param teams: Team data, defaults to None
    :type teams: Optional[Teams], optional
    """

    time: float

    delta_real_time: Optional[float] = None

    game_control_data: Optional[GameControlData] = None

    ball: Optional[Ball] = None
    teams: Optional[Teams] = None
    # collision_matrix: Optional[ForcefulContactMatrix] = None  # TODO: Implement this
