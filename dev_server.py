"""
dev_server.py -- run the Vercel app on your own computer (no Vercel needed).

    pip install -r requirements.txt uvicorn
    python dev_server.py            -> http://localhost:8000
Uses data/responses.csv unless DATABASE_URL is set.
"""
from pathlib import Path

import uvicorn
from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import app

PUBLIC = Path(__file__).parent / "public"


@app.get("/{page}")
def page(page: str):          # mimic Vercel "cleanUrls": /results -> results.html
    for f in (PUBLIC / f"{page}.html", PUBLIC / page):
        if f.is_file():
            return FileResponse(f)
    raise HTTPException(404)


app.mount("/", StaticFiles(directory=PUBLIC, html=True), name="static")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
