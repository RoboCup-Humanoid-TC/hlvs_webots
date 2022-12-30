from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class Field:
    """Static information about a field.

    :param location_id: Id of the location
    :type location_id: str
    :param location_name: Name of the location
    :type location_name: str
    :param size: Size of the field in m
    :type size: Tuple[int, int]
    :param friction: Friction of the field, defaults to None
    :type friction: Optional[float], optional
    :param natural_light: Whether the field has natural light, defaults to None
    :type natural_light: Optional[bool], optional
    :param weather: Weather of the field, defaults to None
    :type weather: Optional[str], optional
    """

    location_id: str
    location_name: str
    size: Tuple[int, int]
    friction: Optional[float] = None
    natural_light: Optional[bool] = None
    weather: Optional[str] = None
