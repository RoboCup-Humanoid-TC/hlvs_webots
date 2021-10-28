from forceful_contact_matrix import ForcefulContactMatrix
from types import SimpleNamespace


class Game(SimpleNamespace):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.penalty_shootout_count = 0
        self.penalty_shootout_goal = False
        self.penalty_shootout_time_to_score = [None, None, None, None, None, None, None, None, None, None]
        self.penalty_shootout_time_to_reach_goal_area = [None, None, None, None, None, None, None, None, None, None]
        self.penalty_shootout_time_to_touch_ball = [None, None, None, None, None, None, None, None, None, None]
        self.ball = self.blackboard.supervisor.getFromDef('BALL')
        self.ball_radius = 0.07 if field_size == 'kid' else 0.1125
        self.ball_kick_translation = [0, 0,
                                      self.ball_radius + self.field.turf_depth]  # initial position of ball before kick
        self.ball_translation = self.blackboard.supervisor.getFromDef('BALL').getField('translation')
        self.ball_exit_translation = None
        self.ball_last_touch_time = 0
        self.ball_first_touch_time = 0
        self.ball_last_touch_time_for_display = 0
        self.ball_position = [0, 0, 0]
        self.ball_last_move = 0
        self.real_time_multiplier = 1000 / (
                    self.minimum_real_time_factor * int(self.supervisor.getBasicTimeStep())) if self.minimum_real_time_factor > 0 else 10
        self.interruption = None
        self.interruption_countdown = 0
        self.interruption_step = None
        self.interruption_step_time = 0
        self.interruption_team = None
        self.interruption_seconds = None
        self.dropped_ball = False
        self.overtime = False
        self.finished_overtime = False
        self.ready_countdown = 0  # simulated time countdown before ready state (used in kick-off after goal and dropped ball)
        self.play_countdown = 0
        self.in_play = None
        self.throw_in = False  # True while throwing in to allow ball handling
        self.throw_in_ball_was_lifted = False  # True if the throwing-in player lifted the ball
        self.over = False
        self.wait_for_state = 'INITIAL'
        self.wait_for_sec_state = None
        self.wait_for_sec_phase = None
        self.forceful_contact_matrix = ForcefulContactMatrix(len(red_team['players']), len(blue_team['players']),
                                                             FOUL_PUSHING_PERIOD, FOUL_PUSHING_TIME, int(self.supervisor.getBasicTimeStep()))
