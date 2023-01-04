from dataclasses import dataclass


@dataclass(frozen=True)
class StaticMatchObject:
    """Static information about a match object.

    :param id: Unique id of the object
    :type id: str
    :param mass: Mass of the object in kg
    :type mass: float
    """

    id: str
    mass: float


@dataclass
class MatchObject:
    """Match object.

    :param id: Unique id of the object
    :type id: str
    """

    id: str
