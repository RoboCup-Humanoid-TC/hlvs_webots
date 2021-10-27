from types import SimpleNamespace

import yaml


class Blackboard:
    def __init__(self, supervisor, game, time):
        self.supervisor = supervisor
        self.game = game
        self.time = time
        with open('referee_config.yaml') as f:
            config = yaml.load(f)
        self.config = SimpleNamespace(**config)
