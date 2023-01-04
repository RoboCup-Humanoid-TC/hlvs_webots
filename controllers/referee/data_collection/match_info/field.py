from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Field:
    """Static information about a field.

    :param location_id: Id of the location
    :type location_id: str
    :param location_name: Name of the location
    :type location_name: str
    :param size_x: Size of the field in x direction
    :type size_x: int
    :param size_y: Size of the field in y direction
    :type size_y: int
    :param friction: Friction of the field, defaults to None
    :type friction: Optional[float], optional
    :param natural_light: Whether the field has natural light, defaults to None
    :type natural_light: Optional[bool], optional
    :param weather: Weather of the field, defaults to None
    :type weather: Optional[str], optional
    """

    location_id: str
    location_name: str
    size_x: int
    size_y: int
    friction: Optional[float] = None
    natural_light: Optional[bool] = None
    weather: Optional[str] = None
