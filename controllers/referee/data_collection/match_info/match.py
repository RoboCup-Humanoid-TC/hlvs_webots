from typing import List

from .static_match_info import StaticMatchInfo
from .step import Step


class Match:
    def __init__(self, static: StaticMatchInfo) -> None:
        """Holds static and dynamic data about a match.

        :param static: Static match info
        :type static: StaticMatchInfo
        """
        self._static: StaticMatchInfo = static

        self._id: str = self._static.id

        self._steps: List[Step] = []

    def get_static_match_info(self) -> StaticMatchInfo:
        """Get the static match info.

        :return: Static match info
        :rtype: StaticMatchInfo
        """
        return self._static

    def get_steps(self) -> List[Step]:
        """Get the steps of the match.

        :return: Steps of the match
        :rtype: List[Step]
        """
        return self._steps

    def add_step(self, step: Step) -> None:
        """Add a step to the match.

        :param step: Step data
        :type step: Step
        """
        self._steps.append(step)

    def current_step(self) -> Step:
        """Get the current step.

        :raises Exception: If there are no steps in the match
        :return: Current step
        :rtype: Step
        """
        if len(self._steps) == 0:
            raise Exception("No steps in match")
        return self._steps[-1]
