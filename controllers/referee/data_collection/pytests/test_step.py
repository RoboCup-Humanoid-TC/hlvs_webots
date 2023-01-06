import data_collection.match_info as mi

# from forceful_contact_matrix import ForcefulContactMatrix


def _create_step(id: int = 42) -> mi.Step:
    time: int = 42 * 8
    time_to_calculate_simulation: int = 30
    ball: mi.Ball = mi.Ball(
        "ball_id",
        mi.Frame("BALL_SHAPE", mi.Pose(mi.Position(0, 0, 0), mi.Rotation(0, 0, 0, 1))),
    )
    player: mi.Player = mi.Player(
        "player_1",
        mi.State.UNKNOWN_STATE,
        mi.Role.ROLE_UNDEFINED,
        mi.Action.ACTION_UNDEFINED,
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
        mi.Frame(
            "camera",
            mi.Pose(mi.Position(0, 0, 0), mi.Rotation(0, 0, 0, 1)),
        ),
    )
    teams: mi.Teams = mi.Teams(
        mi.Team("HSV", player1=player), mi.Team("St. Pauli", player2=player)
    )
    # collision_matrix: ForcefulContactMatrix = ForcefulContactMatrix(
    #     len(teams.team1.players), len(teams.team2.players), 1, 1, 1
    # )

    step = mi.Step(
        id, time, time_to_calculate_simulation, ball, teams
    )  # , collision_matrix)

    assert step.id == id
    assert step.time == time
    assert step.time_to_calculate_simulation == time_to_calculate_simulation
    assert step.ball == ball
    assert step.teams == teams
    # assert step.collision_matrix == collision_matrix

    return step


def test_create_step():
    assert _create_step() is not None


def test_convert_steps_to_dataframe():
    import pandas as pd

    steps = [_create_step(i) for i in range(10)]

    df = pd.json_normalize([step.to_dict() for step in steps])

    assert len(df) == len(steps)


if __name__ == "__main__":
    test_create_step()
    test_convert_steps_to_dataframe()
