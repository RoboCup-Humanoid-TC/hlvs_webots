import os
import time
from datetime import datetime
from threading import Event, Thread

from data_collection import match_info as mi

# from ..logger import Logger


class DataCollector:
    def __init__(
        self,
        save_dir: os.PathLike,
        autosave_interval: int,
        match: mi.Match,
        logger=None,
    ) -> None:
        """Initialize DataCollector.
        :param save_dir: Path to directory where to store match data
        :type save_dir: os.PathLike
        :param autosave_interval: Interval in seconds to autosave match data. Set to -1 to disable autosave
        :type autosave_interval: int
        :param match: Match data
        :type match: mi.Match
        :param logger: Logger, defaults to None
        :type logger: Optional[Logger], optional
        """
        self.save_dir: os.PathLike = save_dir
        self.logger = logger
        self.match: mi.Match = match

        if not os.path.exists(save_dir):
            os.makedirs(save_dir)

        self._finalized = (
            False  # True, if finalized was successful, to prevent saving two times
        )

        self.autosave_interval: int = autosave_interval
        if autosave_interval >= 0:
            self.autosave_stop_tread_event: Event = Event()
            self.autosave_thread: Thread = Thread(
                target=self._autosave,
                args=[
                    self.autosave_stop_tread_event,
                    self.autosave_interval,
                    self.save_dir,
                    self.logger,
                ],
            )
            self.autosave_thread.start()

    def _close(self, filename_state: str):
        """Stop autosave thread and save one last time manually.

        :param filename_state: State to include in save filenames (e.g. "COMPLETE", "FAILURE")
        :type filename_state: str
        """
        # Stop autosave thread
        self.autosave_stop_tread_event.set()
        self.autosave_thread.join()

        # Save match data
        self.match.save(
            self.save_dir,
            f"referee_data_collection_{filename_state}_{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}",
            self.logger,
        )

    def __del__(self) -> None:  # Cleanup in case of failures
        if not self._finalized:
            self._close("FAILURE")

    def finalize(self) -> None:
        """Finalize the data collection and save to filesystem."""
        self._close("COMPLETE")
        self._finalized = True

    def create_new_step(self, time: int) -> None:
        """Creates a new empty step.

        :param time: Time of the step in milliseconds
        :type time: int
        """
        self.match.add_step(mi.Step(time=time))

    def current_step(self) -> mi.Step:
        """Get the current step.

        :return: Current step
        :rtype: mi.Step
        """
        return self.match.current_step()

    def _autosave(
        self,
        stop_event: Event,
        autosave_interval: int,
        save_dir: os.PathLike,
        logger=None,
    ) -> None:
        """Saves match data automatically in AUTOSAVE_INTERVAL.
        Old autosave files are being removed after new autosave was successful.

        :param stop_event: Event to stop autosave thread
        :type stop_event: Event
        :param autosave_interval: Interval in seconds to autosave match data
        :type autosave_interval: int
        :param save_dir: Path to directory where to store match data
        :type save_dir: os.PathLike
        :param logger: Logger, defaults to None
        :type logger: Optional[Logger], optional
        """
        previous_autosave_filename: str = ""  # Path to last autosave filename
        next_autosave_time: float = time.time() + autosave_interval
        while not stop_event.is_set():
            # Sleep for shorter time than autosave interval to join thread faster
            time.sleep(3)
            now: float = time.time()
            if now >= next_autosave_time:
                next_autosave_time = now + autosave_interval
                filename: str = f"referee_data_collection_AUTOSAVE_{datetime.utcnow().strftime('%Y-%m-%dT%H-%M-%S')}"
                self.match.save(save_dir, filename, logger)

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
