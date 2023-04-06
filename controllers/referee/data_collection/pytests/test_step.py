import data_collection.match_info as mi

# from forceful_contact_matrix import ForcefulContactMatrix


def _create_step(time: int) -> mi.Step:
    delta_real_time: float = 0.1

    game_control_data = mi.GameControlData(
        game_state=mi.GameControlData.GameState.STATE_INITIAL,
        first_half=True,
        kickoff_team=1,
        secondary_state=mi.GameControlData.SecondaryGameState.STATE_UNKNOWN,
        secondary_state_info_team=1,
        secondary_state_info_sub_state=1,
        drop_in_team=True,
        drop_in_time=0,
        seconds_remaining=0,
        secondary_seconds_remaining=0,
    )

    ball: mi.Ball = mi.Ball(
        "ball_id",
        mi.Frame("BALL_SHAPE", mi.Pose(mi.Position(0, 0, 0), mi.Rotation(0, 0, 0, 1))),
    )
    player: mi.Player = mi.Player(
        "player_1",
        mi.Frame(
            "base_link",
            mi.Pose(mi.Position(0, 0, 0), mi.Rotation(0, 0, 0, 1)),
        ),
        mi.Frame(
            "l_sole",
            mi.Pose(mi.Position(0, 0, 0), mi.Rotation(0, 0, 0, 1)),
        ),
        mi.Frame(
            "r_sole",
            mi.Pose(mi.Position(0, 0, 0), mi.Rotation(0, 0, 0, 1)),
        ),
        mi.Frame(
            "l_gripper",
            mi.Pose(mi.Position(0, 0, 0), mi.Rotation(0, 0, 0, 1)),
        ),
        mi.Frame(
            "r_gripper",
            mi.Pose(mi.Position(0, 0, 0), mi.Rotation(0, 0, 0, 1)),
        ),
        camera_frame=mi.Frame(
            "camera",
            mi.Pose(mi.Position(0, 0, 0), mi.Rotation(0, 0, 0, 1)),
        ),
        state=mi.State.UNKNOWN_STATE,
        role=mi.Role.ROLE_UNDEFINED,
        action=mi.Action.ACTION_UNDEFINED,
        robot_info=mi.RobotInfo(
            mi.Penalty.UNKNOWN,
            secs_till_unpenalized=42,
            number_of_warnings=42,
            number_of_yellow_cards=42,
            number_of_red_cards=42,
            goalkeeper=False
        )
    )
    teams: mi.Teams = mi.Teams(
        mi.Team("HSV", player1=player), mi.Team("St. Pauli", player2=player)
    )

    step = mi.Step(
        time,
        delta_real_time=delta_real_time,
        ball=ball,
        teams=teams,
    )

    assert step.time == time
    assert step.delta_real_time == delta_real_time
    assert step.ball == ball
    assert step.teams == teams

    return step


def test_create_step():
    assert _create_step(0) is not None


def test_convert_steps_to_dataframe():
    import pandas as pd

    steps = [_create_step(i) for i in range(10)]

    df = pd.json_normalize([step.to_dict() for step in steps])

    assert len(df) == len(steps)


if __name__ == "__main__":
    test_create_step()
    test_convert_steps_to_dataframe()
