from typing import Optional

import data_collection.match_info as mi

# Define test objects in global scope
id: str = "test_id"
match_type: Optional[mi.MatchType] = None
simulation: Optional[mi.Simulation] = None
field: Optional[mi.Field] = None
ball: Optional[mi.StaticBall] = None
teams: Optional[mi.StaticTeams] = None
static_match_info: Optional[mi.StaticMatchInfo] = None

# Create a test StaticMatchInfo object
def test_create_static_match_info():
    global id, match_type, simulation, field, ball, teams, static_match_info
    match_type = mi.MatchType.NORMAL
    simulation = mi.Simulation(True, 0)
    field = mi.Field("test_location_id", "test_location_name", 6, 9, 1.0)
    ball = mi.StaticBall("test_ball_id", 0.5, "test_ball_texture", 0.14)
    teams = mi.StaticTeams(
        mi.StaticTeam("test_team_1", "test_team_1_name", mi.TeamColor.RED),
        mi.StaticTeam("test_team_2", "test_team_2_name", mi.TeamColor.BLUE),
    )

    static_match_info = mi.StaticMatchInfo(
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
    json_static_match_info = mi.StaticMatchInfo.from_json(json_string)

    assert (
        json_static_match_info == static_match_info
    ), f"StaticMatchInfo does not match:\nFROM JSON: {json_static_match_info}\nFROM OBJECT: {static_match_info}"


if __name__ == "__main__":
    test_create_static_match_info()
    test_json_dump_ans_load_static_match_info()
