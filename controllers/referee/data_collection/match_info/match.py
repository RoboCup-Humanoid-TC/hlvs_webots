import os
from typing import List

import pandas as pd

from .static_match_info import StaticMatchInfo
from .step import Step


class Match:
    def __init__(self, static: StaticMatchInfo) -> None:
        """Holds static and dynamic data about a match.

        :param static: Static match info
        :type static: StaticMatchInfo
        """
        self._static: StaticMatchInfo = static

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

    def save(
        self,
        save_dir: os.PathLike,
        file_name: str,
        logger=None,
        also_as_pickle: bool = True,
    ) -> None:
        """Save match as a dataframe to filesystem.

        :param save_dir: Path to directory where to store match data
        :type save_dir: os.PathLike
        :param file_name: Name under which to store the match data (without file extension)
        :type file_name: str
        :param logger: Logger, defaults to None
        :type logger: Optional[Logger], optional
        :param also_as_pickle: Whether dynamic match data should also be saved as a pickle file, defaults to True
        :type also_as_pickle: bool, optional
        """
        if logger:
            logger.info(f"Saving data collection to '{save_dir}' as '{file_name}.*'...")

        # Save static match info
        json_data: str = self.get_static_match_info().to_json()
        with open(os.path.join(save_dir, file_name + ".json"), "w") as f:
            f.write(json_data)

        # Save dynamic match info
        steps = self.get_steps()
        if steps:
            df: pd.DataFrame = pd.json_normalize([step.to_dict() for step in steps])
            df.to_feather(os.path.join(save_dir, file_name + ".feather"))
            if also_as_pickle:
                df.to_pickle(os.path.join(save_dir, file_name + ".pkl"))
