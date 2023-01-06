import os
import time
from datetime import datetime
from threading import Event, Thread

import pandas as pd

# from controller import Supervisor
from data_collection.match_info import Match


class DataCollector:
    def __init__(
        self,
        save_dir: os.PathLike,
        autosave_interval: int,
        # supervisor: Supervisor,
        match: Match,
    ) -> None:
        """Initialize DataCollector.
        :param save_dir: Path to directory where to store match data
        :type save_dir: os.PathLike
        :param autosave_interval: Interval in seconds to autosave match data. Set to -1 to disable autosave
        :type autosave_interval: int
        :param supervisor: Webots supervisor controller to receive match data from
        :type supervisor: Supervisor
        :param match: Match data
        :type match: Match
        """
        self.save_dir: os.PathLike = save_dir
        # self.sv: Supervisor = supervisor
        self.match: Match = match

        self.autosave_interval: int = autosave_interval
        if autosave_interval >= 0:
            self.autosave_stop_tread_event: Event = Event()
            self.autosave_thread: Thread = Thread(
                target=_autosave,
                args=[
                    self.autosave_stop_tread_event,
                    self.autosave_interval,
                    self.save_dir,
                    self.match,
                ],
            )
            self.autosave_thread.start()

    def __del__(self) -> None:  # Cleanup in case of failures
        self.finalize()

    def collect_step(self) -> None:
        """Collect data for current step."""
        pass

    def finalize(self) -> None:
        """Finalize the data collection and save to filesystem."""
        # Stop autosave thread
        self.autosave_stop_tread_event.set()
        self.autosave_thread.join()

        # Save match data
        save(
            self.save_dir,
            self.match,
            f"referee_data_collection_complete_{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}",
        )


def save(
    save_dir: os.PathLike, match: Match, file_name: str, also_as_pickle: bool = True
) -> None:
    """Save match as a dataframe to filesystem.

    :param save_dir: Path to directory where to store match data
    :type save_dir: os.PathLike
    :param data: Match data to save
    :type data: Match
    :param file_name: Name under which to store the match data (without file extension)
    :type file_name: str
    :param also_as_pickle: Whether dynamic match data should also be saved as a pickle file
    """
    # Save static match info
    json_data: str = match.get_static_match_info().to_json()
    with open(os.path.join(save_dir, file_name + ".json"), "w") as f:
        f.write(json_data)

    # Save dynamic match info
    steps = match.get_steps()
    if steps:
        df: pd.DataFrame = pd.json_normalize([step.to_dict() for step in steps])
        df.to_feather(os.path.join(save_dir, file_name + ".feather"))
        if also_as_pickle:
            df.to_pickle(os.path.join(save_dir, file_name + ".pkl"))


def _autosave(
    stop_event: Event, autosave_interval: int, save_dir: os.PathLike, match: Match
) -> None:
    """Saves match data automatically in AUTOSAVE_INTERVAL.
    Old autosave files are being removed after new autosave was successful.

    :param stop_event: Event to stop autosave thread
    :type stop_event: Event
    :param autosave_interval: Interval in seconds to autosave match data
    :type autosave_interval: int
    :param save_dir: Path to directory where to store match data
    :type save_dir: os.PathLike
    :param data: Match data to save
    :type data: DataCollector
    """
    previous_autosave_filename: str = ""  # Path to last autosave filename
    next_autosave_time: float = time.time() + autosave_interval
    while not stop_event.is_set():
        # Sleep for shorter time than autosave interval to join thread faster
        time.sleep(3)
        now: float = time.time()
        if now >= next_autosave_time:
            next_autosave_time = now + autosave_interval
            filename: str = f"referee_data_collection_autosave_{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}"
            save(save_dir, match, filename)

            # Remove previous autosave file
            if previous_autosave_filename:
                for extension in [".feather", ".pkl", ".json"]:
                    try:
                        os.remove(
                            os.path.join(
                                save_dir, previous_autosave_filename + extension
                            )
                        )
                    except FileNotFoundError:
                        pass

            previous_autosave_filename = filename
