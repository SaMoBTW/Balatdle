"""Checks the three acceptance criteria of US-1 against a throwaway database.

Usage:  createdb balatdle_test && python test_seed.py
"""
import json
from pathlib import Path

import psycopg

from seed import ROSTER, seed

SCHEMA = Path(__file__).resolve().parent.parent / "schema.sql"


def count(conn):
    return conn.execute("SELECT count(*) FROM jokers").fetchone()[0]


with psycopg.connect("dbname=balatdle_test", autocommit=True) as conn:
    conn.execute("DROP TABLE IF EXISTS guesses, users, daily_puzzles, jokers CASCADE")
    conn.execute(SCHEMA.read_text())
    roster = json.loads(ROSTER.read_text(encoding="utf-8"))

    # an empty database gets the full roster
    seed(conn, roster)
    assert count(conn) == len(roster) == 150, count(conn)

    # a second run updates rows instead of duplicating them
    seed(conn, roster)
    assert count(conn) == 150, count(conn)

    # a bad rarity fails with a clear error and writes nothing, not even the valid joker before it
    bad = [{**roster[0], "name": "Valid Newcomer"}, {**roster[1], "name": "Broken Joker", "rarity": "Epic"}]
    try:
        seed(conn, bad)
        raise AssertionError("bad rarity was accepted")
    except ValueError as e:
        assert "Broken Joker" in str(e) and "rarity" in str(e), e
    assert count(conn) == 150, count(conn)

print("US-1 checks passed: full load, no duplicates on rerun, bad rarity rejected cleanly.")
