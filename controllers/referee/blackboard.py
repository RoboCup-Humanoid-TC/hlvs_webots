from types import SimpleNamespace

import yaml


class Blackboard:
    def __init__(self, supervisor, game, time, config):
        self.supervisor = supervisor
        self.game = game
        self.time = time
        self.config = config
