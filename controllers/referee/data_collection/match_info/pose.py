from dataclasses import dataclass
from typing import Tuple

import transforms3d
from dataclasses_json import DataClassJsonMixin


@dataclass(frozen=True)
class Position(DataClassJsonMixin):
    """Position of an object in 3D space.

    :param x: X coordinate of the position
    :type x: float
    :param y: Y coordinate of the position
    :type y: float
    :param z: Z coordinate of the position
    :type z: float
    """

    x: float
    y: float
    z: float


@dataclass(frozen=True)
class Rotation(DataClassJsonMixin):
    """Rotation of an object in 3D space as a quaternion.

    :param x: X component of the quaternion
    :type x: float
    :param y: Y component of the quaternion
    :type y: float
    :param z: Z component of the quaternion
    :type z: float
    :param w: W component of the quaternion
    :type w: float
    """

    x: float
    y: float
    z: float
    w: float

    def quaternion(self) -> Tuple[float, float, float, float]:
        """Return the quaternion as a tuple.

        :return: Quaternion in the order [x, y, z, w]
        :rtype: Tuple[float, float, float, float]
        """
        return (self.x, self.y, self.z, self.w)

    def rpy(self) -> Tuple[float, float, float]:
        """Convert rotation to euler angles.

        :return: Euler angles in the order [roll, pitch, yaw]
        :rtype: Tuple[float, float, float]
        """
        return transforms3d.euler.quat2euler((self.x, self.y, self.z, self.w))


@dataclass(frozen=True)
class Pose(DataClassJsonMixin):
    """Pose of an object in 3D space.

    :param position: Position of the object
    :type position: Position
    :param rotation: Rotation of the object
    :type rotation: Rotation
    """

    position: Position
    rotation: Rotation


def pose_from_affine(affine: np.ndarray) -> Pose:
    """Convert a 4x4 or 16(x1) affine matrix to a Pose.

    :param affine: Affine matrix
    :type affine: np.ndarray
    :return: Pose
    :rtype: Pose
    """
    # Reshape 16x1 to 4x4
    if affine.shape == (16,):
        affine = affine.reshape(4, 4)

    position = Position(affine[0, 3], affine[1, 3], affine[2, 3])
    rotation = Rotation(*transforms3d.quaternions.mat2quat(affine[:3, :3]))
    return Pose(position, rotation)
