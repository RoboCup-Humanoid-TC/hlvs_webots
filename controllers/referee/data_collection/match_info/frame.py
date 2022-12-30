from dataclasses import dataclass

from data_collection.match_info.pose import Pose


@dataclass(frozen=True)
class Frame:
    """Frame of a match object in 3D space.

    :param id: Unique id of the frame
    :type id: str
    :param pose: Pose of the frame
    :type pose: Pose
    """

    id: str
    pose: Pose
