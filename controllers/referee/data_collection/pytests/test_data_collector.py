import glob
import os
import time

from controller import Supervisor
from data_collection import match_info as mi
from data_collection.data_collector import DataCollector
from data_collection.pytests.test_static import _create_static_match_info
from data_collection.pytests.test_step import _create_step


def _create_data_collector(tmp_path) -> DataCollector:
    save_dir = tmp_path

    supervisor = Supervisor()
    match = mi.Match(_create_static_match_info())

    data_collector = DataCollector(save_dir, 5, supervisor, match)

    assert data_collector.save_dir == save_dir
    assert data_collector.match == match
    assert data_collector.autosave_interval == 5
    assert data_collector.match.get_static_match_info() == match.get_static_match_info()
    assert data_collector.match.get_steps() == match.get_steps() == []

    return data_collector


def test_create_data_collector(tmp_path):
    d = _create_data_collector(tmp_path)
    # Check for empty directory before first autosave
    assert len(os.listdir(d.save_dir)) == 0

    time.sleep(10)

    # Check if data was saved
    assert (
        len(os.listdir(d.save_dir))
        == len(
            glob.glob(
                os.path.join(d.save_dir, "referee_data_collection_autosave_*.json")
            )
        )
        == 1
    ), "Only a static match info file should be saved (referee_data_collection_autosave_*.json)"

    # Add a few steps to the match
    for i in range(5):
        d.match.add_step(_create_step(i))

    time.sleep(10)

    # Check if data was saved
    assert (
        len(os.listdir(d.save_dir))
        == len(
            glob.glob(os.path.join(d.save_dir, "referee_data_collection_autosave_*"))
        )
        == 3
    ), "A static match info .json file and two dynamic match info (.feather and .pkl) file should be saved"

    # Close data collector
    d.finalize()

    # Check if data was saved
    assert (
        len(os.listdir(d.save_dir)) == 6
    ), "Six files (.json, .feather and .pkl) should be saved, tree for each autosave and one for the final save"
    assert (
        len(glob.glob(os.path.join(d.save_dir, "referee_data_collection_complete_*")))
        == 3
    ), "Three files should be saved for the final save (referee_data_collection_complete_* [.json, .feather and .pkl])"


# TODO: Test data collector failure case (__del__)


if __name__ == "__main__":
    test_create_data_collector("REPLACE_WITH_PATH")
