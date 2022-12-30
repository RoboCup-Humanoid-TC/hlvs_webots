from dataclasses import dataclass
from enum import StrEnum, unique

from data_collection.match_info.ball import StaticBall
from data_collection.match_info.field import Field
from data_collection.match_info.simulation import Simulation
from data_collection.match_info.team import StaticTeams
from dataclasses_json import DataClassJsonMixin


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
    :param match_type: Type of this match (KnockOut, RoundRobin, DropIn)
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
