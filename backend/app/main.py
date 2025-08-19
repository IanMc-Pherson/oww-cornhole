from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict
import uuid
import random
import string

app = FastAPI(title="Cornhole Tournament API")


# --- Data Models ---


class Player(BaseModel):
    name: str
    contact: Optional[str] = None


class TeamCreate(BaseModel):
    team_name: str
    players: List[Player]
    captain_contact: Optional[str] = None


class MatchCreate(BaseModel):
    match_id: str = Field(..., alias="matchId")
    round: int
    index: int
    teamA_id: Optional[str] = None
    teamB_id: Optional[str] = None
    next_match_id: Optional[str] = None
    next_slot: Optional[str] = None


class Score(BaseModel):
    a: int
    b: int


class ScoreSubmit(BaseModel):
    score: Score


# --- In-memory store ---

STORE: Dict[str, Dict] = {"tournaments": {}}


def _get_tournament(tid: str) -> Dict:
    return STORE["tournaments"].setdefault(tid, {"teams": {}, "matches": {}})


# --- Routes ---


@app.get("/health")
def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.post("/t/{tid}/teams")
def create_team(tid: str, payload: TeamCreate):
    tourn = _get_tournament(tid)
    team_id = f"tm_{uuid.uuid4().hex[:4]}"
    team_code = "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    team = {
        "teamId": team_id,
        "team_name": payload.team_name,
        "players": [p.model_dump() for p in payload.players],
        "captain_contact": payload.captain_contact,
        "team_code": team_code,
    }
    tourn["teams"][team_id] = team
    return {"ok": True, "data": {"teamId": team_id, "team_code": team_code}}


@app.get("/t/{tid}/teams")
def list_teams(tid: str):
    tourn = _get_tournament(tid)
    return {"teams": list(tourn["teams"].values())}


@app.post("/t/{tid}/matches")
def create_match(tid: str, payload: MatchCreate):
    tourn = _get_tournament(tid)
    if payload.teamA_id and payload.teamA_id not in tourn["teams"]:
        raise HTTPException(status_code=404, detail="teamA not found")
    if payload.teamB_id and payload.teamB_id not in tourn["teams"]:
        raise HTTPException(status_code=404, detail="teamB not found")
    match = {
        "matchId": payload.match_id,
        "round": payload.round,
        "index": payload.index,
        "teamA_id": payload.teamA_id,
        "teamB_id": payload.teamB_id,
        "status": "scheduled",
        "score": {"a": 0, "b": 0},
        "winner_team_id": None,
        "next_match_id": payload.next_match_id,
        "next_slot": payload.next_slot,
    }
    tourn["matches"][payload.match_id] = match
    return match


@app.get("/t/{tid}/matches")
def list_matches(tid: str):
    tourn = _get_tournament(tid)
    return {"matches": list(tourn["matches"].values())}


@app.post("/t/{tid}/matches/{match_id}/score")
def submit_score(tid: str, match_id: str, payload: ScoreSubmit):
    tourn = _get_tournament(tid)
    match = tourn["matches"].get(match_id)
    if not match:
        raise HTTPException(status_code=404, detail="match not found")
    if match["status"] not in {"scheduled", "playing"}:
        raise HTTPException(status_code=400, detail="match not in scorable state")
    score = payload.score
    if score.a < 0 or score.b < 0 or score.a == score.b:
        raise HTTPException(status_code=400, detail="invalid score")
    match["score"] = {"a": score.a, "b": score.b}
    match["status"] = "final"
    winner_team_id = match["teamA_id"] if score.a > score.b else match["teamB_id"]
    match["winner_team_id"] = winner_team_id
    if match.get("next_match_id"):
        next_match = tourn["matches"].get(match["next_match_id"])
        if next_match:
            if match.get("next_slot") == "A":
                next_match["teamA_id"] = winner_team_id
            elif match.get("next_slot") == "B":
                next_match["teamB_id"] = winner_team_id
    return {"ok": True, "data": {"winner_team_id": winner_team_id}}
