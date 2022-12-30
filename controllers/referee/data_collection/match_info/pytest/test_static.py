from typing import Optional

import data_collection.match_info as ma

# Define test objects in global scope
id: str = "test_id"
match_type: Optional[ma.MatchType] = None
simulation: Optional[ma.Simulation] = None
field: Optional[ma.Field] = None
ball: Optional[ma.StaticBall] = None
teams: Optional[ma.StaticTeams] = None
static_match_info: Optional[ma.StaticMatchInfo] = None

# Create a test StaticMatchInfo object
def test_create_static_match_info():
    global id, match_type, simulation, field, ball, teams, static_match_info
    match_type = ma.MatchType.NORMAL
    simulation = ma.Simulation(True, 0)
    field = ma.Field("test_location_id", "test_location_name", (6, 9), 1.0)
    ball = ma.StaticBall("test_ball_id", 0.5, "test_ball_texture", 0.14)
    teams = ma.StaticTeams(
        ma.StaticTeam("test_team_1", "test_team_1_name", ma.TeamColor.RED),
        ma.StaticTeam("test_team_2", "test_team_2_name", ma.TeamColor.BLUE),
    )

    static_match_info = ma.StaticMatchInfo(
        id, match_type, simulation, field, ball, teams
    )

    assert static_match_info.id == id
    assert static_match_info.match_type == match_type
    assert static_match_info.simulation == simulation
    assert static_match_info.field == field
    assert static_match_info.ball == ball
    assert static_match_info.teams == teams


def test_json_dump_ans_load_static_match_info():
    # Dump the object to a JSON string
    json_string = static_match_info.to_json()  # type: ignore

    # Load the object from the JSON string
    json_static_match_info = ma.StaticMatchInfo.from_json(json_string)

    assert (
        json_static_match_info == static_match_info
    ), f"StaticMatchInfo does not match:\nFROM JSON: {json_static_match_info}\nFROM OBJECT: {static_match_info}"


if __name__ == "__main__":
    test_create_static_match_info()
    test_json_dump_ans_load_static_match_info()
