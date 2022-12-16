from typing import List

from data_collection.match_info.player import Player


class Teams:
    def __init__(self):
        self.A: Team
        self.B: Team


class Team:
    def __init__(self, id: int, name: str, color: str):
        """Holds data about a team.
        :param id: Team id
        :type id: int
        :param name: Team name
        :type name: str
        :param color: Team color
        :type color: str
        """
        self.id: int = id
        self.name: str = name
        self.color: str = color

        self.players: List[Player] = []
