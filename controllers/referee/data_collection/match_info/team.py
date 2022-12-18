from typing import List
from enum import Enum, unique


from data_collection.match_info.player import Player


@unique
class TeamColor(Enum):
    """Enum for team colors."""

    RED = "red"
    BLUE = "blue"


class Team:
    def __init__(self, id: int, name: str, color: TeamColor):
        """Holds data about a team.
        :param id: Team id
        :type id: int
        :param name: Team name
        :type name: str
        :param color: Team color
        :type color: TeamColor
        """
        self.id: int = id
        self.name: str = name
        self.color: TeamColor = color

        self.players: List[Player] = []

        def set_players(self, players: List[Player]) -> None:
            """Set the players of the team.

            :param players: Players of the team
            :type players: List[Player]
            """
            self.players = players

        def get_player_by_id(self, id: int) -> Player:
            """Returns the player with the given id.

            :param id: Id of the player
            :type id: int
            :return: Player with the given id
            :rtype: Player
            :raises ValueError: If no player with the given id exists
            """
            for player in self.players:
                if player.id == id:
                    return player
            raise ValueError(f"Player with id {id} not found")


class Teams:
    def __init__(self, A: Team, B: Team) -> None:
        """Holds data about both teams.

        :param A: Team A
        :type A: Team
        :param B: Team B
        :type B: Team
        """
        self.A: Team = A
        self.B: Team = B
        self.teams: List[Team] = [self.A, self.B]

    def get_team_by_id(self, id: int) -> Team:
        """Returns the team with the given id.

        :param id: Id of the team
        :type id: int
        :return: Team with the given id
        :rtype: Team
        :raises ValueError: If no team with the given id exists
        """
        for team in self.teams:
            if team.id == id:
                return team
        raise ValueError(f"Team with id {id} not found")

    def get_team_by_color(self, color: TeamColor) -> Team:
        """Returns the team with the given color.

        :param color: Color of the team
        :type color: TeamColor
        :return: Team with the given color
        :rtype: Team
        :raises ValueError: If no team with the given color exists
        """
        for team in self.teams:
            if team.color == color:
                return team
        raise ValueError(f"Team with color {color} not found")

    def red(self) -> Team:
        """Returns the red team.

        :return: Red team
        :rtype: Team
        :raises ValueError: If no red team exists
        """
        return self.get_team_by_color(TeamColor.RED)

    def blue(self) -> Team:
        """Returns the blue team.

        :return: Blue team
        :rtype: Team
        :raises ValueError: If no blue team exists
        """
        return self.get_team_by_color(TeamColor.BLUE)

    def get_team_by_name(self, name: str) -> Team:
        """Returns the team with the given name.

        :param name: Name of the team
        :type name: str
        :return: Team with the given name
        :rtype: Team
        :raises ValueError: If no team with the given name exists
        """
        for team in self.teams:
            if team.name == name:
                return team
        raise ValueError(f"Team with name {name} not found")
