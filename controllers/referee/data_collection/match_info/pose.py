from typing import Tuple

import transforms3d


class Position:
    def __init__(self, x: float, y: float, z: float):
        """Initialize Position.

        :param x: x coordinate of the position
        :type x: float
        :param y: y coordinate of the position
        :type y: float
        :param z: z coordinate of the position
        :type z: float
        """
        self.x = x
        self.y = y
        self.z = z


class Rotation:
    def __init__(self, x: float, y: float, z: float, w: float):
        """Initialize Rotation as a quaternion.

        :param x: x component of the quaternion
        :type x: float
        :param y: y component of the quaternion
        :type y: float
        :param z: z component of the quaternion
        :type z: float
        :param w: w component of the quaternion
        :type w: float
        """
        self.quaternion = [x, y, z, w]

    def rpy(self) -> Tuple[float, float, float]:
        """Convert rotation to euler angles.

        :return: Euler angles in the order [roll, pitch, yaw]
        :rtype: Tuple[float, float, float]
        """
        return transforms3d.euler.quat2euler(self.quaternion)


class Pose:
    def __init__(self, position: Position, rotation: Rotation) -> None:
        """Initialize Pose.

        :param position: Position of the pose
        :type position: Position
        :param rotation: Rotation of the pose
        :type rotation: Rotation
        """
        self.position = position
        self.rotation = rotation
