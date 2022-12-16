from typing import Tuple


class Field:
    def __init__(self) -> None:
        self.location_id: int
        self.location_name: str
        self.size: Tuple[int]
        # TODO: Evaluate:
        self.weather: str
        self.friction: float
        self.natural_light: bool
