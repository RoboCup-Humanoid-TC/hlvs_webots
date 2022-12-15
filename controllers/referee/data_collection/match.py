from typing import List

import os
import pandas as pd

from .step import Step

class Match:
    def __init__(self, save_dir: str) -> None:
        """Holds data about a match.

        :param save_dir: Path to directory where to store match data
        :type save_dir: str
        """
        self.save_dir : str = save_dir
        
        self.rows : List[Step] = []

    def get_match(self) -> List[Step]:
        return self.rows

    def save(self, file_name: str, also_as_pickle: bool = True) -> None:
        """Save match as a dataframe to filesystem.

        :param file_name: Name under which to store the dataframe (without file extension)
        :type file_name: str
        :param also_as_pickle: Whether match data should also be saved as a pickle file
        """
        df : pd.DataFrame = pd.DataFrame(self.rows)
        df.to_feather(os.path.join(self.save_dir, file_name + ".feather"))
        if also_as_pickle:
            df.to_pickle(os.path.join(self.save_dir, file_name + ".pkl"))
