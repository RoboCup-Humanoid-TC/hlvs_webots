from typing import Optional

from data_collection.match_info.pose import Pose


class Frame:
    def __init__(self, id: str) -> None:
        """Initialize Frame.

        :param id: ID of the frame (e.g. "base_link")
        :type id: str
        """
        self.id: str = id

        self.pose: Optional[Pose] = None

    def set_pose(self, pose: Pose) -> None:
        """Set pose of the frame.

        :param pose: Pose of the frame
        :type pose: Pose
        """
        self.pose = pose
