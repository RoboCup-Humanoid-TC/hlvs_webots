from dataclasses import dataclass
from typing import Tuple

from data_collection.match_info.frame import Frame


# class CameraMatrix:
# def __init__(self) -> None:
# pass
#
# def get_field_of_view(self, resolution: Tuple[int, int]) -> Tuple[float, float]:
# return (0.0, 0.0)  # TODO


@dataclass(frozen=True)
class Camera:
    """Static information about a camera.

    :param frame_id: Id of the frame that this camera is attached to
    :type frame_id: str
    :param FPS: Frames per second
    :type FPS: float
    :param FOV: Field of view of the camera
    :type FOV: float
    :param resolution: Resolution of the camera
    :type resolution: Tuple[int, int]
    """

    frame_id: str
    FPS: float
    FOV: float
    resolution: Tuple[int, int]
