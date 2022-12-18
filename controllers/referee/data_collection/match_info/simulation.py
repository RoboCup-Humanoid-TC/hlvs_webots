class Simulation:
    def __init__(self, is_simulated: bool, basic_time_step: int) -> None:
        """Holds data about a match simulation.

        :param is_simulated: Whether the match is simulated
        :type is_simulated: bool
        :param basic_time_step: Basic time step of the simulation in ms
        :type basic_time_step: int
        """
        self.is_simulated: bool = is_simulated
        self.basic_time_step: int = basic_time_step
