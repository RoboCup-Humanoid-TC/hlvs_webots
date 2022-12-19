import os
import time
from datetime import datetime
from threading import Thread

import pandas as pd
from controller import Supervisor
from data_collection.match import Match

AUTOSAVE_INTERVAL: int = 2 * 60  # in seconds


class DataCollector:
    def __init__(self, save_dir: str, supervisor: Supervisor, match: Match) -> None:
        """Initialize DataCollector.
        :param save_dir: Path to directory where to store match data
        :type save_dir: str
        :param supervisor: Webots supervisor controller to receive match data from
        :type supervisor: Supervisor
        :param match: Match data
        :type match: Match
        """
        self.save_dir: str = save_dir
        self.sv: Supervisor = supervisor
        self.match: Match = match

        self.autosave_tread_active: bool = True
        self.autosave_thread: Thread = Thread(
            target=_autosave, args=[self.match, self.autosave_tread_active]
        )

    def collect_step(self) -> None:
        """Collect data for current step."""
        pass

    def finalize(self) -> None:
        """Finalize the data collection and save to filesystem."""
        # Stop autosave thread
        self.autosave_tread_active = False
        self.autosave_thread.join()

        # Save match data
        save(
            self.save_dir,
            f"referee_data_collection_complete_{datetime.now().astimezone().isoformat()}",
        )


def save(save_dir: str, file_name: str, also_as_pickle: bool = True) -> None:
    """Save match as a dataframe to filesystem.

    :param save_dir: Path to directory where to store match data
    :type save_dir: str
    :param file_name: Name under which to store the dataframe (without file extension)
    :type file_name: str
    :param also_as_pickle: Whether match data should also be saved as a pickle file
    """
    # TODO: Save meta data
    df: pd.DataFrame = pd.DataFrame()  # TODO: Create dataframe from match data
    df.to_feather(os.path.join(save_dir, file_name + ".feather"))
    if also_as_pickle:
        df.to_pickle(os.path.join(save_dir, file_name + ".pkl"))


def _autosave(save_dir: str, data: DataCollector, is_active: bool) -> None:
    """Saves match data automatically in AUTOSAVE_INTERVAL.

    :param save_dir: Path to directory where to store match data
    :type save_dir: str
    :param data: Match data to save
    :type data: DataCollector
    :param is_active: Whether autosave thread should be active
    :type is_active: bool
    """
    next_autosave_time: float = time.time() + AUTOSAVE_INTERVAL
    while is_active:  # Set to False to stop autosave thread
        time.sleep(
            5
        )  # Sleep for shorter time than autosave interval to join thread faster
        now: float = time.time()
        if now >= next_autosave_time:
            next_autosave_time = now + AUTOSAVE_INTERVAL
            save(
                save_dir,
                f"referee_data_collection_autosave_{datetime.now().astimezone().isoformat()}",
            )
