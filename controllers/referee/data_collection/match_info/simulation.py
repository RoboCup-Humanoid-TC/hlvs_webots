from dataclasses import dataclass


# TODO: collection information about the match (docker hash, commit hash, etc.)


@dataclass(frozen=True)
class Simulation:
    """Holds data about a match simulation.

    :param is_simulated: Whether the match is simulated
    :type is_simulated: bool
    :param basic_time_step: Basic time step of the simulation in ms
    :type basic_time_step: int
    :param data_collection_interval: Interval of steps when data is collected. Example: 8 means every 8th step is collected: current_step % data_collection_interval == 0
    :type data_collection_interval: int
    """

    is_simulated: bool
    basic_time_step: int
    data_collection_interval: int
