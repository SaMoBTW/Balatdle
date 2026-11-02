"""Checks the backend side of US-2 to US-6 against a throwaway database.

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
assert first.status_code == 200 and first.get_json() == second.get_json() == {"date": "2026-10-11", "number": 1, "max_guesses": 8}

# the response carries the date and number only, never the answer
assert set(first.get_json()) == {"date", "number", "max_guesses"}
assert answer_name not in first.get_data(as_text=True)

# the next day is a different, later puzzle
api.today = lambda: DAY + timedelta(days=1)
assert client.get("/api/puzzle").get_json() == {"date": "2026-10-12", "number": 2, "max_guesses": 8}

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


# suggestions get every joker's name, rarity and effect text, and nothing else
listing = client.get("/api/jokers").get_json()["jokers"]
assert len(listing) == 150 and all(set(j) == {"name", "rarity", "effect"} for j in listing)
assert next(j for j in listing if j["name"] == "Blueprint") == {
    "name": "Blueprint", "rarity": "Rare", "effect": "Copies ability of Joker to the right"}
names = {"names": [j["name"] for j in listing]}

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

# ---- US-5: win the round ----
# a wrong guess is not a win; the right one is, and it names the answer and the guess count
assert first.get_json()["solved"] is False
assert second.get_json()["solved"] is True and second.get_json()["name"] == answer_name
assert second.get_json()["number"] == 2

# once solved, the server refuses more guesses for that player and does not count them
other = next(n for n in names["names"] if n not in (answer_name, wrong))
after_win = guess(other)
assert after_win.status_code == 409 and "already solved" in after_win.get_json()["error"]
with db.connect() as conn:
    assert conn.execute("SELECT count(*) FROM guesses g JOIN users u ON u.id = g.user_id"
                        " WHERE u.token = 'player-one'").fetchone()[0] == 2

# another player can still play
assert guess(other, token="player-two").status_code == 201

# ---- US-6: pick up where I left off ----
def progress(token):
    return client.post("/api/progress", json={"token": token})


def players():
    with db.connect() as conn:
        return {r[0] for r in conn.execute("SELECT token FROM users")}


# a first visit creates the player record before any guess is made
assert "fresh-visitor" not in players()
fresh = progress("fresh-visitor")
assert fresh.status_code == 200 and fresh.get_json() == {"guesses": []}
assert "fresh-visitor" in players()

# a mid-round reload gets back every guess with the same feedback it had when it was made
mid = progress("player-two").get_json()["guesses"]
assert [g["number"] for g in mid] == [1, 2] and not any(g["solved"] for g in mid)

# returning after a win restores the finished round, including the winning guess
done = progress("player-one").get_json()["guesses"]
assert [g["name"] for g in done] == [wrong, answer_name] and done[-1]["solved"]
assert done[0] == first.get_json() and done[1] == second.get_json()

# the next day starts empty for the same player
api.today = lambda: DAY + timedelta(days=1)
assert progress("player-one").get_json() == {"guesses": []}
api.today = lambda: DAY

# no token, no record
assert client.post("/api/progress", json={}).status_code == 400

# the players table holds an anonymous token and game counts, nothing personal
with db.connect() as conn:
    columns = {r[0] for r in conn.execute(
        "SELECT column_name FROM information_schema.columns WHERE table_name = 'users'")}
assert columns == {"id", "token", "created_at", "current_streak", "max_streak", "games_played", "games_won"}, columns

# ---- guess limit: 8 per player per day ----
wrongs = [n for n in names["names"] if n != answer_name][:9]
for i, name in enumerate(wrongs[:8], start=1):
    r = guess(name, token="unlucky")
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    if i < 8:
        # the answer stays hidden while the round is still going
        assert body["lost"] is False and "answer" not in body and answer_name not in r.get_data(as_text=True)
# the eighth miss ends the round and reveals the answer
assert body["lost"] is True and body["answer"] == answer_name
# a ninth guess is refused and not counted
ninth = guess(wrongs[8], token="unlucky")
assert ninth.status_code == 409 and "out of guesses" in ninth.get_json()["error"]
restored = progress("unlucky").get_json()["guesses"]
assert len(restored) == 8 and restored[-1]["lost"] and restored[-1]["answer"] == answer_name

print("US-2 to US-6 and guess-limit backend checks passed.")
