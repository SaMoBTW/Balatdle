"""Checks the backend side of US-2 against a throwaway database.

Usage:  createdb balatdle_test && python test_app.py
"""
import json
import os
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

os.environ["DATABASE_URL"] = "dbname=balatdle_test"

import app as api  # noqa: E402  (must import after DATABASE_URL is set)
import db  # noqa: E402
from schedule import GAP, schedule  # noqa: E402
from seed import ROSTER, seed  # noqa: E402

SCHEMA = Path(__file__).resolve().parent.parent / "schema.sql"
DAY = date(2026, 10, 11)

with db.connect(autocommit=True) as conn:
    conn.execute("DROP TABLE IF EXISTS guesses, users, daily_puzzles, jokers CASCADE")
    conn.execute(SCHEMA.read_text())
    seed(conn, json.loads(ROSTER.read_text(encoding="utf-8")))

    # the schedule never reuses a joker within GAP days
    assert schedule(conn, DAY, 400, random.Random(1)) == 400
    rows = conn.execute("SELECT puzzle_date, joker_id FROM daily_puzzles ORDER BY puzzle_date").fetchall()
    last_seen = {}
    for day, joker in rows:
        assert joker not in last_seen or (day - last_seen[joker]).days > GAP, (day, joker)
        last_seen[joker] = day

    # running it again leaves dates that already have an answer alone
    assert schedule(conn, DAY, 400, random.Random(2)) == 0
    assert conn.execute("SELECT puzzle_date, joker_id FROM daily_puzzles ORDER BY puzzle_date").fetchall() == rows
    answer_name = conn.execute(
        "SELECT name FROM jokers JOIN daily_puzzles ON joker_id = id WHERE puzzle_date = %s", [DAY]).fetchone()[0]

# the date rolls over at 00:00 UTC, whatever the player's own time zone is
est = timezone(timedelta(hours=-5))
assert api.today(datetime(2026, 10, 11, 23, 59, tzinfo=timezone.utc)) == date(2026, 10, 11)
assert api.today(datetime(2026, 10, 12, 0, 0, tzinfo=timezone.utc)) == date(2026, 10, 12)
assert api.today(datetime(2026, 10, 11, 19, 0, tzinfo=est)) == date(2026, 10, 12)  # 7pm in New York is already tomorrow

client = api.app.test_client()
api.today = lambda: DAY

# two players on the same date get the same puzzle
first, second = client.get("/api/puzzle"), client.get("/api/puzzle")
assert first.status_code == 200 and first.get_json() == second.get_json() == {"date": "2026-10-11", "number": 1}

# the response carries the date and number only, never the answer
assert set(first.get_json()) == {"date", "number"}
assert answer_name not in first.get_data(as_text=True)

# the next day is a different, later puzzle
api.today = lambda: DAY + timedelta(days=1)
assert client.get("/api/puzzle").get_json() == {"date": "2026-10-12", "number": 2}

# a day with nothing scheduled is a clear error, not a crash
api.today = lambda: DAY - timedelta(days=1)
missing = client.get("/api/puzzle")
assert missing.status_code == 503 and "No puzzle" in missing.get_json()["error"]

print("US-2 backend checks passed: same puzzle all day, UTC rollover, no answer in the response, no repeats within {} days.".format(GAP))
