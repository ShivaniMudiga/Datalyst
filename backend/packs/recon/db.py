"""The reconciliation pack's own connection.

Deliberately not the app's pools. Those exist to keep the *model* read-only
against a user's database; this pack is operator-side code that owns the
settlement tables and writes to them. Different job, different connection.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DSN = os.getenv("RECON_DSN", "postgresql://apple@localhost:5432/kartly")


@contextmanager
def cursor(commit: bool = False):
    with psycopg.connect(DSN, row_factory=dict_row) as connection:
        with connection.cursor() as cur:
            yield cur
        if commit:
            connection.commit()
