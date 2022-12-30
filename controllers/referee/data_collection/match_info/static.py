from dataclasses import dataclass
from enum import Enum, unique

from data_collection.match_info.ball import StaticBall
from data_collection.match_info.field import Field
from data_collection.match_info.simulation import Simulation


@unique
class MatchType(Enum):
    """Match type enum."""

    NORMAL = "NORMAL"
    KNOCKOUT = "KNOCKOUT"
    PENALTY = "PENALTY"
    DROPIN = "DROPIN"


@dataclass(frozen=True)
class StaticMatchInfo:
    """Static information about a match.

    :param id: Match id
    :type id: str
    :param match_type: Type of this match (KnockOut, RoundRobin, DropIn)
    :type match_type: MatchType
    :param simulation: Simulation data
    :type simulation: Simulation
    :param field: Field data
    :type field: Field
    :param ball: Ball data
    :type ball: StaticBall
    """

    id: str
    match_type: MatchType
    simulation: Simulation
    field: Field
    ball: StaticBall
