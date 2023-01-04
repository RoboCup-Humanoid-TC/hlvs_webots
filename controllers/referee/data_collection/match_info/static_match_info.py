from dataclasses import dataclass
from enum import StrEnum, unique

from dataclasses_json import DataClassJsonMixin

from .ball import StaticBall
from .field import Field
from .simulation import Simulation
from .team import StaticTeams


@unique
class MatchType(StrEnum):  # Inherit from str to make it JSON serializable
    """Match type enum."""

    NORMAL = "NORMAL"
    KNOCKOUT = "KNOCKOUT"
    PENALTY = "PENALTY"
    DROPIN = "DROPIN"


@dataclass(frozen=True)
class StaticMatchInfo(DataClassJsonMixin):
    """Static information about a match.

    :param id: Match id
    :type id: str
    :param match_type: Type of this match (Normal, KnockOut, RoundRobin, DropIn)
    :type match_type: MatchType
    :param simulation: Simulation data
    :type simulation: Simulation
    :param field: Field data
    :type field: Field
    :param ball: Ball data
    :type ball: StaticBall
    :param teams: Team data
    :type teams: StaticTeams
    """

    id: str
    match_type: MatchType
    simulation: Simulation
    field: Field
    ball: StaticBall
    teams: StaticTeams
