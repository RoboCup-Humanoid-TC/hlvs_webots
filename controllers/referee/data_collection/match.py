from typing import List

from data_collection.step import Step


class Match:
    def __init__(self) -> None:
        """Holds data about a match."""
        self.steps: List[Step] = []
