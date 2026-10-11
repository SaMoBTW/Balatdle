"""Load the joker roster from jokers.json into the jokers table.

Usage:  python seed.py
Connects to DATABASE_URL, or the local "balatdle" database if it is not set.
Running it again updates existing jokers instead of adding duplicates, so a
balance patch is an edit to jokers.json followed by another run.
"""
import json
import os
import sys
from pathlib import Path

import psycopg

ROSTER = Path(__file__).with_name("jokers.json")
COLUMNS = ("name", "rarity", "cost", "effect_type", "activation", "scales", "unlock_method")

UPSERT = "INSERT INTO jokers ({cols}) VALUES ({vals}) ON CONFLICT (name) DO UPDATE SET {sets}".format(
    cols=", ".join(COLUMNS),
    vals=", ".join(["%s"] * len(COLUMNS)),
    sets=", ".join("{0} = EXCLUDED.{0}".format(c) for c in COLUMNS[1:]),
)


def seed(conn, roster):
    """Upsert every joker in one transaction, so a bad entry leaves the table untouched."""
    with conn.transaction(), conn.cursor() as cur:
        for joker in roster:
            try:
                cur.execute(UPSERT, [joker[c] for c in COLUMNS])
            except KeyError as e:
                raise ValueError("joker {!r} is missing the field {}".format(joker.get("name", "?"), e))
            except psycopg.errors.IntegrityError as e:
                raise ValueError("joker {!r} was rejected: {}".format(joker.get("name", "?"), e.diag.message_primary))
    return len(roster)


def main():
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))
    with psycopg.connect(os.environ.get("DATABASE_URL", "dbname=balatdle")) as conn:
        try:
            count = seed(conn, roster)
        except ValueError as e:
            sys.exit("Seed failed, nothing was written. " + str(e))
        total = conn.execute("SELECT count(*) FROM jokers").fetchone()[0]
    print("Seeded {} jokers ({} in the table).".format(count, total))


if __name__ == "__main__":
    main()
