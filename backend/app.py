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


def token_from(body):
    """The browser's anonymous player token, or None if it is missing or malformed."""
    token = body.get("token")
    return token if isinstance(token, str) and 0 < len(token) <= 64 else None


def player_id(conn, token):
    """Find the player for this token, creating the record on a first visit."""
    return conn.execute(
        "INSERT INTO users (token) VALUES (%s) ON CONFLICT (token) DO UPDATE SET token = EXCLUDED.token"
        " RETURNING id", [token]).fetchone()[0]


def joker_by_id(joker_id):
    return next(j for j in roster().values() if j["id"] == joker_id)


def result(joker, number, answer_id):
    """One guess as the page shows it. On a win the guessed joker is the answer,
    so naming it reveals nothing early (NFR-1)."""
    return dict(name=joker["name"], number=number, solved=joker["id"] == answer_id,
                feedback=compare(joker, joker_by_id(answer_id)))


@app.post("/api/progress")
def progress():
    """Register the browser's player on page load and return today's guesses, so a reload
    or a return visit picks up where it left off. Only the token is stored; no personal details."""
    token = token_from(request.get_json(silent=True) or {})
    if token is None:
        return jsonify(error="Missing player token."), 400
    day = today()
    with db.connect() as conn:
        user_id = player_id(conn, token)
        answer = conn.execute("SELECT joker_id FROM daily_puzzles WHERE puzzle_date = %s", [day]).fetchone()
        rows = conn.execute(
            "SELECT joker_id, guess_number FROM guesses WHERE user_id = %s AND puzzle_date = %s"
            " ORDER BY guess_number", [user_id, day]).fetchall()
    if answer is None:
        return jsonify(guesses=[])
    return jsonify(guesses=[result(joker_by_id(j), n, answer[0]) for j, n in rows])


@app.post("/api/guess")
def guess():
    body = request.get_json(silent=True) or {}
    token, name = token_from(body), body.get("name")
    if token is None:
        return jsonify(error="Missing player token."), 400
    if not isinstance(name, str) or not name.strip():
        return jsonify(error="Type a joker name first."), 400

    joker = roster().get(name.strip().casefold())
    if joker is None:
        return jsonify(error="\u201c{}\u201d isn\u2019t a joker.".format(name.strip()[:40])), 400

    day = today()
    with db.connect() as conn:
        answer = conn.execute("SELECT joker_id FROM daily_puzzles WHERE puzzle_date = %s", [day]).fetchone()
        if answer is None:
            return jsonify(error="No puzzle is scheduled for today."), 503
        user_id = player_id(conn, token)
        solved = conn.execute(
            "SELECT 1 FROM guesses WHERE user_id = %s AND puzzle_date = %s AND is_correct",
            [user_id, day]).fetchone()
        if solved:
            return jsonify(error="You already solved today\u2019s puzzle."), 409
        repeat = conn.execute(
            "SELECT 1 FROM guesses WHERE user_id = %s AND puzzle_date = %s AND joker_id = %s",
            [user_id, day, joker["id"]]).fetchone()
        if repeat:
            return jsonify(error="You already guessed {}.".format(joker["name"])), 409
        # ponytail: two submits from the same player at the same instant can race on guess_number;
        # the UNIQUE constraint stops a duplicate and the frontend blocks double submits.
        number = conn.execute(
            "INSERT INTO guesses (user_id, puzzle_date, joker_id, guess_number, is_correct)"
            " SELECT %s, %s, %s, coalesce(max(guess_number), 0) + 1, %s FROM guesses"
            " WHERE user_id = %s AND puzzle_date = %s RETURNING guess_number",
            [user_id, day, joker["id"], joker["id"] == answer[0], user_id, day]).fetchone()[0]
    return jsonify(result(joker, number, answer[0])), 201
