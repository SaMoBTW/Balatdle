import os

import psycopg


def connect(**kwargs):
    """Connect to DATABASE_URL, or the local "balatdle" database if it is not set."""
    return psycopg.connect(os.environ.get("DATABASE_URL", "dbname=balatdle"), **kwargs)
