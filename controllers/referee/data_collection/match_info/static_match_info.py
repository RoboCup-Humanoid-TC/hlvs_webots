from dataclasses import dataclass
from enum import Enum, unique

from dataclasses_json import DataClassJsonMixin

from .ball import StaticBall
from .field import Field
from .simulation import Simulation
from .team import StaticTeams


@unique
class MatchType(Enum, str):  # Inherit from str to make it JSON serializable
    """Match type enum."""

    NORMAL = "NORMAL"
    KNOCKOUT = "KNOCKOUT"
    PENALTY = "PENALTY"
    DROPIN = "DROPIN"


@unique
class LeagueSubType(Enum, str):  # Inherit from str to make it JSON serializable
    """League sub type enum."""

    KID = "KID"
    ADULT = "ADULT"


@dataclass(frozen=True)
class StaticMatchInfo(DataClassJsonMixin):
    """Static information about a match.

    :param id: Match id
    :type id: str
    :param match_type: Type of this match (Normal, KnockOut, RoundRobin, DropIn)
    :type match_type: MatchType
    :param league_sub_type: Sub type of this match (Kid, Adult)
    :type league_sub_type: LeagueSubType
    :param simulation: Simulation data
    :type simulation: Simulation
    :param field: Field data
    :type field: Field
    :param ball: Ball data
    :type ball: StaticBall
    :param teams: Team data
    :type teams: StaticTeams
    :param version: Version of the match_info package
    :type version: str
    """

    id: str
    match_type: MatchType
    league_sub_type: LeagueSubType
    simulation: Simulation
    field: Field
    ball: StaticBall
    teams: StaticTeams

    version: str = "0.0.1"
