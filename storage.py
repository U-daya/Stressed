"""
storage.py -- Saves and loads survey responses.

  * PostgresStore : used on Vercel. Reads the DATABASE_URL environment variable
                    that the Neon integration (Vercel Marketplace) sets
                    automatically. Responses persist permanently.
  * CSVStore      : local file, for running/testing on a laptop without a database.
"""
from __future__ import annotations

import os
import threading
from pathlib import Path

import pandas as pd

import config as C

_LOCK = threading.Lock()

# SQL column types for each stored column
_SQL_TYPES = {"timestamp": "TEXT", "response_id": "TEXT PRIMARY KEY", "q1_dept": "TEXT",
              "classification": "TEXT", "stress_index": "DOUBLE PRECISION"}


def _sql_type(col: str) -> str:
    return _SQL_TYPES.get(col, "DOUBLE PRECISION")


class PostgresStore:
    name = "Postgres database"
    table = "responses"

    def __init__(self, url: str):
        import psycopg
        self._psycopg = psycopg
        self.url = url
        cols = ", ".join(f"{c} {_sql_type(c)}" for c in C.COLUMNS)
        with self._conn() as con:
            con.execute(f"CREATE TABLE IF NOT EXISTS {self.table} ({cols}, "
                        f"created_at TIMESTAMPTZ DEFAULT now())")
            # if questions were added to config.py later, add the missing columns
            for c in C.COLUMNS:
                con.execute(f"ALTER TABLE {self.table} ADD COLUMN IF NOT EXISTS {c} "
                            f"{_sql_type(c).replace(' PRIMARY KEY', '')}")

    def _conn(self):
        # prepare_threshold=None keeps it compatible with Neon's pooled (PgBouncer) URL
        return self._psycopg.connect(self.url, autocommit=True, prepare_threshold=None,
                                     connect_timeout=10)

    def append(self, row: dict) -> None:
        cols = ", ".join(C.COLUMNS)
        ph = ", ".join(["%s"] * len(C.COLUMNS))
        with self._conn() as con:
            con.execute(f"INSERT INTO {self.table} ({cols}) VALUES ({ph})",
                        [row.get(c) for c in C.COLUMNS])

    def load(self) -> pd.DataFrame:
        with self._conn() as con:
            cur = con.execute(f"SELECT {', '.join(C.COLUMNS)} FROM {self.table} "
                              f"ORDER BY created_at")
            return pd.DataFrame(cur.fetchall(), columns=C.COLUMNS)


class CSVStore:
    name = "Local CSV file"

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            pd.DataFrame(columns=C.COLUMNS).to_csv(self.path, index=False)

    def append(self, row: dict) -> None:
        with _LOCK:
            pd.DataFrame([row], columns=C.COLUMNS).to_csv(
                self.path, mode="a", header=False, index=False)

    def load(self) -> pd.DataFrame:
        return pd.read_csv(self.path)


_store = None


def get_store():
    """Postgres if DATABASE_URL (or POSTGRES_URL) is set, otherwise a local CSV."""
    global _store
    if _store is None:
        url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")
        if url:
            _store = PostgresStore(url)
        elif os.environ.get("VERCEL"):
            raise RuntimeError("No database connected. In Vercel: Storage -> Neon -> "
                               "connect to this project, then redeploy.")
        else:
            _store = CSVStore(os.environ.get("STRESS_CSV", "data/responses.csv"))
    return _store
