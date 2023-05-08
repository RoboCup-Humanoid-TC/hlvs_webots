from dataclasses import dataclass

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
    :param pixel_count_x: Number of pixels in x direction
    :type pixel_count_x: int
    :param pixel_count_y: Number of pixels in y direction
    :type pixel_count_y: int
    """

    frame_id: str
    FPS: float
    FOV: float
    pixel_count_x: int
    pixel_count_y: int
