from typing import Optional, Tuple


class Field:
    def __init__(
        self,
        location_id: int,
        location_name: str,
        size: Tuple[int, int],
        friction: Optional[float] = None,
        natural_light: Optional[bool] = None,
        weather: Optional[str] = None,
    ) -> None:
        """Initialize Field.

        :param location_id: Id of the location
        :type location_id: int
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
        self.location_id: int = location_id
        self.location_name: str = location_name
        self.size: Tuple[int, int] = size
        self.friction: Optional[float] = friction
        self.natural_light: Optional[bool] = natural_light
        self.weather: Optional[str] = weather
