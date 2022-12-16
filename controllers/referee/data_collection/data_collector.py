import time
from datetime import datetime
from threading import Thread

from controller import Supervisor

from .match import Match

"""
TODOs
~~~~~
- Collect and store meta data
"""

AUTOSAVE_INTERVAL : int = 2 * 60  # in seconds

def _autosave(match: Match, is_active: bool) -> None:
    """Saves match data automatically in AUTOSAVE_INTERVAL.

    :param Match: Match data to save
    :type Match: List[Step]
    :param is_active: Flag to indicate if autosave should be active
    :type is_active: bool
    """
    next_autosave_time : float = time.time() + AUTOSAVE_INTERVAL
    while is_active:  # Set to False to stop autosave thread
        time.sleep(5)  # Sleep for shorter time than autosave interval to join thread faster
        now : float = time.time()
        if now >= next_autosave_time:
            next_autosave_time = now + AUTOSAVE_INTERVAL
            match.save(f"referee_data_collection_autosave_{datetime.now().astimezone().isoformat()}")


class DataCollector:
    def __init__(self, save_dir: str, supervisor: Supervisor) -> None:
        """Initialize DataCollector.
        :param save_dir: Path to directory where to store match data
        :type save_dir: str
        :param supervisor: Webots supervisor controller to receive match data from
        :type supervisor: Supervisor
        """
        self.save_dir: str = save_dir
        self.sv : Supervisor = supervisor

        self.match : Match = Match(self.save_dir)

        self.autosave_tread_active : bool = True
        self.autosave_thread : Thread = Thread(target=_autosave, args=[
            self.match,
            self.autosave_tread_active
            ])

    def collect_step(self) -> None:
        """Collect data for current step."""
        pass

    def finalize(self) -> None:
        """Finalize the data collection and save to filesystem."""
        # Stop autosave thread
        self.autosave_tread_active = False
        self.autosave_thread.join()

        # Save match data
        self.match.save(f"referee_data_collection_complete_{datetime.now().astimezone().isoformat()}")
