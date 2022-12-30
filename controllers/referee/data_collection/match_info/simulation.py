from dataclasses import dataclass


# TODO: collection information about the match (docker hash, commit hash, etc.)


@dataclass(frozen=True)
class Simulation:
    """Holds data about a match simulation.

    :param is_simulated: Whether the match is simulated
    :type is_simulated: bool
    :param basic_time_step: Basic time step of the simulation in ms
    :type basic_time_step: int
    """

    is_simulated: bool
    basic_time_step: int
