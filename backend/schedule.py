"""Assign an answer joker to each upcoming date in daily_puzzles.

Usage:  python schedule.py [days]     (default 365, starting today in UTC)
A date that already has a puzzle keeps it, so a day that has been played never
changes its answer. No joker is reused within GAP days of its last appearance.
"""
import random
import sys
from datetime import timedelta

import db
from app import today

GAP = 100  # ponytail: must stay below the roster size (150) or picks run out


def schedule(conn, start, days, rng=random):
    """Fill start .. start + days - 1. Returns how many dates were added."""
    with conn.transaction():
        ids = [r[0] for r in conn.execute("SELECT id FROM jokers")]
        answers = dict(conn.execute(
            "SELECT puzzle_date, joker_id FROM daily_puzzles WHERE puzzle_date >= %s",
            [start - timedelta(days=GAP)]))
        added = 0
        for i in range(days):
            day = start + timedelta(days=i)
            if day in answers:
                continue
            recent = {answers.get(day - timedelta(days=d)) for d in range(1, GAP + 1)}
            answers[day] = rng.choice([j for j in ids if j not in recent])
            conn.execute("INSERT INTO daily_puzzles (puzzle_date, joker_id) VALUES (%s, %s)", [day, answers[day]])
            added += 1
    return added


if __name__ == "__main__":
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    with db.connect() as conn:
        print("Scheduled {} new puzzles from {}.".format(schedule(conn, today(), days), today()))
