"""AI Buyer API — runs the orchestration pipeline, streams nothing (simple
POST returning the full trace; the frontend renders it as a live feed)."""
from fastapi import APIRouter
from pydantic import BaseModel

from ..agents.buyer import run_buyer

router = APIRouter(prefix="/api/buyer", tags=["buyer"])


class BuyerRequest(BaseModel):
    query: str


@router.post("/run")
def run(request: BuyerRequest):
    if not request.query.strip():
        return {"error": "query required"}
    return run_buyer(request.query.strip())


@router.get("/runs")
def recent_runs(limit: int = 20):
    from .. import db
    conn = db.get_conn()
    rows = [dict(r) for r in conn.execute(
        "SELECT run_id, query, created_at FROM buyer_runs ORDER BY rowid DESC LIMIT ?",
        (limit,))]
    return {"runs": rows}
