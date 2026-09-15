-- Balatdle schema (PostgreSQL)

CREATE TABLE jokers (
    id            INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name          TEXT    NOT NULL UNIQUE,
    rarity        TEXT    NOT NULL CHECK (rarity IN ('Common', 'Uncommon', 'Rare', 'Legendary')),
    cost          INTEGER NOT NULL CHECK (cost >= 0),
    effect_type   TEXT    NOT NULL,  -- e.g. 'Mult', 'Chips', 'XMult', 'Economy', 'Retrigger'
    activation    TEXT    NOT NULL,  -- e.g. 'On Scored', 'On Played', 'Passive', 'End of Round'
    scales        BOOLEAN NOT NULL,
    unlock_method TEXT    NOT NULL   -- e.g. 'Available from start', 'Discover 20 jokers'
);

CREATE TABLE daily_puzzles (
    puzzle_date DATE    PRIMARY KEY,
    joker_id    INTEGER NOT NULL REFERENCES jokers(id)
);

CREATE TABLE users (
    id             INTEGER     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    token          TEXT        NOT NULL UNIQUE,  -- random id kept in the browser, no account
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    current_streak INTEGER     NOT NULL DEFAULT 0,
    max_streak     INTEGER     NOT NULL DEFAULT 0,
    games_played   INTEGER     NOT NULL DEFAULT 0,
    games_won      INTEGER     NOT NULL DEFAULT 0
);

CREATE TABLE guesses (
    id           INTEGER     GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id      INTEGER     NOT NULL REFERENCES users(id),
    puzzle_date  DATE        NOT NULL REFERENCES daily_puzzles(puzzle_date),
    joker_id     INTEGER     NOT NULL REFERENCES jokers(id),
    guess_number INTEGER     NOT NULL CHECK (guess_number > 0),
    is_correct   BOOLEAN     NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, puzzle_date, guess_number)
);

-- the one query the game runs on every page load
CREATE INDEX idx_guesses_user_date ON guesses(user_id, puzzle_date);
