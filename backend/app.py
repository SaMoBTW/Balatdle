"""Balatdle API.

Usage:  .venv/bin/flask --app app run --port 5001
"""
from datetime import datetime, timezone

from flask import Flask, jsonify

import db

app = Flask(__name__)


def today(now=None):
    """The puzzle date. It rolls over at 00:00 UTC, so every player changes day at the same moment."""
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date()


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
