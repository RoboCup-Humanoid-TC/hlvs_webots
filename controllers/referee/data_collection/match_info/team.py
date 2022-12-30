from dataclasses import dataclass
from enum import StrEnum, unique
from typing import List, Tuple

from data_collection.match_info.player import Player


@unique
class TeamColor(StrEnum):  # Inherit from str to make it JSON serializable
    """Enum for team colors."""

    RED = "RED"
    BLUE = "BLUE"


@dataclass(frozen=True)
class StaticTeam:
    """Static information about a team.

    :param id: Team id
    :type id: str
    :param name: Team name
    :type name: str
    :param color: Team color
    :type color: TeamColor
    """

    id: str
    name: str
    color: TeamColor


class Team:
    def __init__(self, id: str):
        """Dynamic data about a team.
        :param id: Team id
        :type id: str
        """
        self.id: str = id

        self.players: List[Player] = []

        def set_players(self, players: List[Player]) -> None:
            """Set the players of the team.

            :param players: Players of the team
            :type players: List[Player]
            """
            self.players = players

        def get_player_by_id(self, id: str) -> Player:
            """Returns the player with the given id.

            :param id: Id of the player
            :type id: str
            :raises ValueError: If no player with the given id exists
            :return: Player with the given id
            :rtype: Player
            """
            for player in self.players:
                if player.id == id:
                    return player
            raise ValueError(f"Player with id {id} not found")


@dataclass(frozen=True)
class StaticTeams:
    """Static information about the teams.

    :param team1: First team
    :type team1: StaticTeam
    :param team2: Second team
    :type team2: StaticTeam
    """

    team1: StaticTeam
    team2: StaticTeam

    def get_teams(self) -> Tuple[StaticTeam, StaticTeam]:
        """Returns the teams.

        :return: Teams
        :rtype: Tuple[StaticTeam, StaticTeam]
        """
        return self.team1, self.team2

    def get_team_by_id(self, id: str) -> StaticTeam:
        """Returns the team with the given id.

        :param id: Id of the team
        :type id: str
        :raises ValueError: If no team with the given id exists
        :return: Team with the given id
        :rtype: StaticTeam
        """
        for team in self.get_teams():
            if team.id == id:
                return team
        raise ValueError(f"Team with id {id} not found")

    def get_team_by_color(self, color: TeamColor) -> StaticTeam:
        """Returns the team with the given color.

        :param color: Color of the team
        :type color: TeamColor
        :raises ValueError: If no team with the given color exists
        :return: Team with the given color
        :rtype: StaticTeam
        """
        for team in self.get_teams():
            if team.color == color:
                return team
        raise ValueError(f"Team with color {color} not found")

    def red(self) -> StaticTeam:
        """Returns the red team.

        :raises ValueError: If no red team exists
        :return: Red team
        :rtype: StaticTeam
        """
        return self.get_team_by_color(TeamColor.RED)

    def blue(self) -> StaticTeam:
        """Returns the blue team.

        :raises ValueError: If no blue team exists
        :return: Blue team
        :rtype: StaticTeam
        """
        return self.get_team_by_color(TeamColor.BLUE)

    def get_team_by_name(self, name: str) -> StaticTeam:
        """Returns the team with the given name.

        :param name: Name of the team
        :type name: str
        :raises ValueError: If no team with the given name exists
        :return: Team with the given name
        :rtype: StaticTeam
        """
        for team in self.get_teams():
            if team.name == name:
                return team
        raise ValueError(f"Team with name {name} not found")


@dataclass(frozen=True)
class Teams:
    """Holds both teams.

    :param team1: First team
    :type team1: Team
    :param team2: Second team
    :type team2: Team
    """

    team1: Team
    team2: Team

    def get_teams(self) -> Tuple[Team, Team]:
        """Returns the teams.

        :return: Teams
        :rtype: Tuple[Team, Team]
        """
        return self.team1, self.team2

    def get_team_by_id(self, id: str) -> Team:
        """Returns the team with the given id.

        :param id: Id of the team
        :type id: str
        :raises ValueError: If no team with the given id exists
        :return: Team with the given id
        :rtype: Team
        """
        for team in self.get_teams():
            if team.id == id:
                return team
        raise ValueError(f"Team with id {id} not found")
