# Balatrodle

Balatrodle is a web-based daily puzzle game where players guess a hidden “joker” from the deck-building video game Balatro. It follows the format of Wordle and similar games like LoLdle and Valdle.

Each day, there is one mystery joker for everyone to solve, and the puzzle resets at a set time.

## How it works

To play, a user types the name of a joker. The game compares that guess to the hidden answer and provides color-coded feedback on several attributes, including:

- rarity
- purchase cost
- effect type
- activation timing
- whether the effect scales
- how the joker is unlocked

A matching attribute turns green, while a partial match turns yellow. For numeric attributes such as cost, an up or down arrow indicates whether the real value is higher or lower.

Players use these clues to narrow down the answer, which usually takes between four and six guesses.

The game also tracks each player’s win streak, generates a spoiler-free result grid that can be shared, and keeps an archive of past puzzles. Since everyone receives the same puzzle each day, players can compare their results with friends.

## Users

The main audience is players of Balatro, along with fans of quick daily guessing games in the Wordle style.

This game works for both:

- dedicated players who can identify obscure jokers from small clues
- newer players who learn the roster as they play

It requires no account and no installation. A user simply opens the page in a browser on a phone or computer and starts playing.

A second group to design for is the returning player, whose streak and statistics are saved between visits without requiring an account.

## Technology and justification

Balatrodle is a full-stack web project with three main components: a user interface, a backend service, and a database.

### Frontend

The user interface will be built with React. This lets me build each piece as a reusable component with its own state, which keeps the code organized as the interface grows. React is also common, well documented, and something I already have experience using.

### Backend

The backend will be a REST API written in Python with Flask. Python is easy to use, and this project only needs a few endpoints:

- get the current day’s puzzle
- check a submitted guess on the server
- return player statistics

### Database

The database will be SQLite, accessed from Python through the built-in sqlite3 module. A relational database fits because the data is structured and connected.

There will be four tables:

- jokers: stores each joker and its attributes
- daily_puzzles: links each date to that day’s answer
- users: stores anonymous player records
- guesses: records each attempt

SQLite works well here because it is serverless and file-based. The entire database is stored in a single file with no separate server to install or run.