class SimTime:
    def __init__(self):
        self.time = 0

    def progress_ms(self, milliseconds):
        self.time += milliseconds

    def get_ms(self):
        return self.time

    def get_sec(self):
        return self.time/1000.0
