from typing import Tuple

from data_collection.match_info.frame import Frame


# class CameraMatrix:
# def __init__(self) -> None:
# pass
#
# def get_field_of_view(self, resolution: Tuple[int, int]) -> Tuple[float, float]:
# return (0.0, 0.0)  # TODO


class Camera:
    def __init__(
        self,
        frame: Frame,
        FPS: float,
        FOV: float,
        resolution: Tuple[int, int],
    ) -> None:
        """Initialize Camera.

        :param frame: Frame of the camera
        :type frame: Frame
        :param FPS: Frames per second
        :type FPS: float
        :param FOV: Field of view of the camera
        :type FOV: float
        :param resolution: Resolution of the camera
        :type resolution: Tuple[int, int]
        """
        self.frame: Frame = frame
        self.FPS: float = FPS
        self.FOV: float = FOV
        self.resolution: Tuple[int, int] = resolution

        # self.camera_matrix: CameraMatrix = CameraMatrix()
