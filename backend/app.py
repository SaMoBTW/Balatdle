"""Balatdle API.

Usage:  .venv/bin/flask --app app run --port 5001
"""
from datetime import datetime, timezone
from functools import lru_cache

from flask import Flask, jsonify, request
from psycopg.rows import dict_row

import db
from evaluate import compare

app = Flask(__name__)


def today(now=None):
    """The puzzle date. It rolls over at 00:00 UTC, so every player changes day at the same moment."""
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()


@lru_cache(maxsize=None)
def roster():
    """Every joker with its attributes, keyed by lowercase name. Loaded once and kept in memory,
    so checking a guessed name never touches the database. ponytail: restart the API after re-seeding."""
    with db.connect(row_factory=dict_row) as conn:
        rows = conn.execute("SELECT id, name, rarity, cost, effect_type, activation, scales, unlock_method FROM jokers")
        return {row["name"].casefold(): row for row in rows}


@app.get("/api/puzzle")
def puzzle():
    day = today()
    with db.connect() as conn:
        # The answer (joker_id) is deliberately never selected, so it cannot reach the browser.
        row = conn.execute(
            "SELECT puzzle_date, puzzle_date - (SELECT min(puzzle_date) FROM daily_puzzles) + 1"
            " FROM daily_puzzles WHERE puzzle_date = %s", [day]).fetchone()
    if row is None:
        return jsonify(error="No puzzle is scheduled for today."), 503
    return jsonify(date=row[0].isoformat(), number=row[1])


@app.get("/api/jokers")
def jokers():
    """Joker names for autocomplete. All 150 are listed, so the list says nothing about the answer."""
    return jsonify(names=sorted(j["name"] for j in roster().values()))


@app.post("/api/guess")
def guess():
    body = request.get_json(silent=True) or {}
    token, name = body.get("token"), body.get("name")
    if not isinstance(token, str) or not 0 < len(token) <= 64:
        return jsonify(error="Missing player token."), 400
    if not isinstance(name, str) or not name.strip():
        return jsonify(error="Type a joker name first."), 400

    joker = roster().get(name.strip().casefold())
    if joker is None:
        return jsonify(error="“{}” isn’t a joker.".format(name.strip()[:40])), 400
    joker_id, joker_name = joker["id"], joker["name"]

    day = today()
    with db.connect() as conn:
        answer = conn.execute("SELECT joker_id FROM daily_puzzles WHERE puzzle_date = %s", [day]).fetchone()
        if answer is None:
            return jsonify(error="No puzzle is scheduled for today."), 503
        user_id = conn.execute(
            "INSERT INTO users (token) VALUES (%s) ON CONFLICT (token) DO UPDATE SET token = EXCLUDED.token"
            " RETURNING id", [token]).fetchone()[0]
        solved = conn.execute(
            "SELECT 1 FROM guesses WHERE user_id = %s AND puzzle_date = %s AND is_correct",
            [user_id, day]).fetchone()
        if solved:
            return jsonify(error="You already solved today\u2019s puzzle."), 409
        repeat = conn.execute(
            "SELECT 1 FROM guesses WHERE user_id = %s AND puzzle_date = %s AND joker_id = %s",
            [user_id, day, joker_id]).fetchone()
        if repeat:
            return jsonify(error="You already guessed {}.".format(joker_name)), 409
        # ponytail: two submits from the same player at the same instant can race on guess_number;
        # the UNIQUE constraint stops a duplicate and the frontend blocks double submits.
        number = conn.execute(
            "INSERT INTO guesses (user_id, puzzle_date, joker_id, guess_number, is_correct)"
            " SELECT %s, %s, %s, coalesce(max(guess_number), 0) + 1, %s FROM guesses"
            " WHERE user_id = %s AND puzzle_date = %s RETURNING guess_number",
            [user_id, day, joker_id, joker_id == answer[0], user_id, day]).fetchone()[0]
    answer_joker = next(j for j in roster().values() if j["id"] == answer[0])
    # On a win the guessed joker is the answer, so naming it here reveals nothing early (NFR-1).
    return jsonify(name=joker_name, number=number, solved=joker_id == answer[0],
                   feedback=compare(joker, answer_joker)), 201
