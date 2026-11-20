"""
app.py -- Backend for the Vercel deployment (one FastAPI app).

Routes (Vercel detects this FastAPI "app" automatically):
  GET  /api/questions   the 10-question questionnaire (from config.py)
  POST /api/submit      validate + save one response, return the classification
  GET  /api/results     all statistical analyses on the current data
  GET  /api/export      download the dataset as CSV (needs ADMIN_PASSWORD)
  GET  /api/health      quick check that the app and database are connected
"""
from __future__ import annotations

import os
import secrets
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from fastapi import FastAPI, Header, HTTPException  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402

import config as C  # noqa: E402
import stats_engine as S  # noqa: E402
import views as V  # noqa: E402
from storage import get_store  # noqa: E402

app = FastAPI(title=C.APP_TITLE, docs_url=None, redoc_url=None)

# Small in-memory cache so many visitors to the results page don't
# recompute everything; cleared whenever a new response arrives.
_cache = {"t": 0.0, "data": None}
CACHE_SECONDS = 20


def _data() -> pd.DataFrame:
    if _cache["data"] is None or time.time() - _cache["t"] > CACHE_SECONDS:
        _cache["data"] = S.clean(get_store().load())
        _cache["t"] = time.time()
    return _cache["data"]


def _validate(body: dict) -> dict:
    """Check every answer against config.py; raise 400 with a clear message."""
    if not isinstance(body, dict):
        raise HTTPException(400, "Invalid request.")
    if not body.get("consent"):
        raise HTTPException(400, "Please tick the consent box to submit.")
    clean, missing = {}, []
    for q in C.QUESTIONS:
        k, v = q["key"], body.get(q["key"])
        if v is None or v == "":
            missing.append(f"Q{q['num']}")
            continue
        if q["kind"] == "category":
            if v not in q["options"]:
                raise HTTPException(400, f"Q{q['num']}: invalid choice.")
            clean[k] = v
        else:
            try:
                x = float(v)
            except (TypeError, ValueError):
                raise HTTPException(400, f"Q{q['num']}: please enter a number.")
            if not (q["lo"] <= x <= q["hi"]):
                raise HTTPException(400, f"Q{q['num']}: must be between {q['lo']} and {q['hi']}.")
            if q["kind"] == "scale" or q.get("integer"):
                if x != int(x):
                    raise HTTPException(400, f"Q{q['num']}: must be a whole number.")
                x = int(x)
            clean[k] = x
    if missing:
        raise HTTPException(400, "Please answer: " + ", ".join(missing))
    return clean


@app.get("/api/questions")
def questions():
    return V.sanitize(V.questions_payload())


@app.post("/api/submit")
def submit(body: dict):
    ans = _validate(body)
    si = C.stress_index(ans["q2_stress"], ans["q3_overwhelm"])
    row = dict(timestamp=datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S"),
               response_id=uuid.uuid4().hex[:12], **ans,
               stress_index=si, classification=C.classify(si))
    try:
        get_store().append(row)
    except Exception as e:
        raise HTTPException(503, f"Your response could not be saved ({type(e).__name__}). Please try again.")
    _cache["data"] = None
    return V.sanitize(V.personal_result(row, _data()))


@app.get("/api/results")
def results():
    store = get_store()
    return JSONResponse(V.sanitize(V.results_payload(_data(), store.name)),
                        headers={"Cache-Control": "no-store"})


@app.get("/api/export")
def export(x_admin_password: str = Header(default="")):
    pw = os.environ.get("ADMIN_PASSWORD")
    if not pw:
        raise HTTPException(403, "ADMIN_PASSWORD is not set in the Vercel project settings.")
    if not secrets.compare_digest(x_admin_password, pw):
        raise HTTPException(401, "Wrong password.")
    raw = get_store().load()
    return Response(raw.to_csv(index=False), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=stress_survey_responses.csv",
                             "Cache-Control": "no-store"})


@app.get("/api/health")
def health():
    try:
        store = get_store()
        n = len(store.load())
        return {"ok": True, "storage": store.name, "rows": n}
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)
