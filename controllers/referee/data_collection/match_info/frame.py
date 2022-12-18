class Frame:
    def __init__(self, id: str) -> None:
        """Initialize Frame.

        :param id: ID of the frame (e.g. "base_link")
        :type id: str
        """
        self.id: str = id
