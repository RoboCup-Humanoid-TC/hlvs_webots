from dataclasses import dataclass
from typing import Optional

from dataclasses_json import DataClassJsonMixin
from forceful_contact_matrix import ForcefulContactMatrix

from .ball import Ball
from .team import Teams


@dataclass
class Step(DataClassJsonMixin):
    """Holds data about a step.

    :param time: Time of step in milliseconds
    :type time: int
    :param time_to_calculate_simulation: Time to calculate simulation in milliseconds, defaults to None
    :type time_to_calculate_simulation: Optional[int], optional
    :param ball: Ball data, defaults to None
    :type ball: Optional[Ball], optional
    :param teams: Team data, defaults to None
    :type teams: Optional[Teams], optional
    :param collision_matrix: Collision matrix, defaults to None
    :type collision_matrix: Optional[ForcefulContactMatrix], optional
    """

    time: int

    time_to_calculate_simulation: Optional[int] = None
    ball: Optional[Ball] = None
    teams: Optional[Teams] = None
    # collision_matrix: Optional[ForcefulContactMatrix] = None
    # TODO: GameController events
