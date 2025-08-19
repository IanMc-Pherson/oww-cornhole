from fastapi.testclient import TestClient
from app.main import app


def create_team(client, tid: str, name: str):
    payload = {
        "team_name": name,
        "players": [{"name": "A"}, {"name": "B"}],
    }
    resp = client.post(f"/t/{tid}/teams", json=payload)
    assert resp.status_code == 200
    return resp.json()["data"]


def test_create_team_and_score_flow():
    client = TestClient(app)
    tid = "t1"

    team_a = create_team(client, tid, "Bag Bandits")
    team_b = create_team(client, tid, "Corn Stars")

    # create next round match
    resp = client.post(
        f"/t/{tid}/matches",
        json={"matchId": "m2", "round": 2, "index": 0},
    )
    assert resp.status_code == 200

    # create first round match with link to next match
    resp = client.post(
        f"/t/{tid}/matches",
        json={
            "matchId": "m1",
            "round": 1,
            "index": 0,
            "teamA_id": team_a["teamId"],
            "teamB_id": team_b["teamId"],
            "next_match_id": "m2",
            "next_slot": "A",
        },
    )
    assert resp.status_code == 200

    # submit score
    resp = client.post(
        f"/t/{tid}/matches/m1/score",
        json={"score": {"a": 21, "b": 15}},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["winner_team_id"] == team_a["teamId"]

    # verify match status and progression
    resp = client.get(f"/t/{tid}/matches")
    matches = {m["matchId"]: m for m in resp.json()["matches"]}
    assert matches["m1"]["status"] == "final"
    assert matches["m2"]["teamA_id"] == team_a["teamId"]
