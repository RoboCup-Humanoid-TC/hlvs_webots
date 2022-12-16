from typing import List, Optional, Tuple

from data_collection.match_info.match_object import MatchObject
from data_collection.match_info.ball import Ball
from data_collection.match_info.team import Team, Teams
from data_collection.match_info.player import Player
from forceful_contact_matrix import ForcefulContactMatrix


class Step:
    def __init__(
        self,
        id: int,
        time: Tuple[int],
        time_to_calculate_simulation: Optional[Tuple[int]] = None,
    ) -> None:
        """Holds data about a step.

        :param id: Step id
        :type id: int
        :param time: Time of step (seconds, milliseconds)
        :type time: Tuple[int]
        :param time_to_calculate_simulation: Time to calculate simulation (seconds, milliseconds)
        :type time_to_calculate_simulation: Optional[Tuple[int]]
        """
        self.id: int = id
        self.time: Tuple[int] = time
        self.time_to_calculate_simulation: Optional[
            Tuple[int]
        ] = time_to_calculate_simulation

        self.ball: Ball
        self.teams: Teams
        self.collision_matrix: ForcefulContactMatrix
        # TODO: GameController events
