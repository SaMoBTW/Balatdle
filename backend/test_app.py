"""Checks the backend side of US-2, US-3 and US-4 against a throwaway database.

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


# ---- US-3: submit a guess by name ----
api.today = lambda: DAY
api.roster.cache_clear()


def guess(name, token="player-one"):
    return client.post("/api/guess", json={"token": token, "name": name})


def guess_count():
    with db.connect() as conn:
        return conn.execute("SELECT count(*) FROM guesses").fetchone()[0]


# autocomplete gets every joker name and nothing else
names = client.get("/api/jokers").get_json()
assert set(names) == {"names"} and len(names["names"]) == 150 and "Blueprint" in names["names"]

# a real name is recorded, matched without caring about case or stray spaces
wrong = next(n for n in names["names"] if n != answer_name)
first = guess("  " + wrong.lower() + " ")
assert first.status_code == 201, first.get_json()
assert {k: first.get_json()[k] for k in ("name", "number")} == {"name": wrong, "number": 1}
second = guess(answer_name)
assert second.status_code == 201 and second.get_json()["number"] == 2
with db.connect() as conn:
    flags = conn.execute("SELECT guess_number, is_correct FROM guesses ORDER BY guess_number").fetchall()
assert flags == [(1, False), (2, True)], flags

# guessing the same joker twice is refused and not counted
repeat = guess(wrong)
assert repeat.status_code == 409 and guess_count() == 2

# a made-up name is rejected before any database connection is opened
real_connect = db.connect
db.connect = lambda **kw: (_ for _ in ()).throw(AssertionError("database touched for a bad name"))
try:
    bad = guess("Jimbo the Great")
finally:
    db.connect = real_connect
assert bad.status_code == 400 and "Jimbo the Great" in bad.get_json()["error"] and guess_count() == 2

# malformed requests are turned away
assert client.post("/api/guess", json={"name": wrong}).status_code == 400
assert guess("   ").status_code == 400
assert client.post("/api/guess", data="not json").status_code == 400

# another player's numbering starts from 1
assert guess(wrong, token="player-two").get_json()["number"] == 1

# ---- US-4: feedback on each guess ----
attrs = ["rarity", "cost", "effect_type", "activation", "scales", "unlock_method"]

# every guess reports all six attributes, each as exact, partial or none
wrong_feedback = first.get_json()["feedback"]
assert [f["attribute"] for f in wrong_feedback] == attrs
assert all(f["match"] in ("exact", "partial", "none") for f in wrong_feedback)
assert "direction" in wrong_feedback[1]

# the answer comes back exact on every attribute
assert {f["match"] for f in second.get_json()["feedback"]} == {"exact"}

# a wrong guess's feedback carries the guessed joker's values, never the answer's name
assert answer_name not in first.get_data(as_text=True)

print("US-2, US-3 and US-4 backend checks passed.")
