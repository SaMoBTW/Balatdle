import { useEffect, useState } from 'react'

export default function App() {
  const [puzzle, setPuzzle] = useState(null)
  const [error, setError] = useState(null)
  const [guess, setGuess] = useState('')

  useEffect(() => {
    fetch('/api/puzzle')
      .then((res) => res.json().then((body) => (res.ok ? body : Promise.reject(body.error))))
      .then(setPuzzle)
      .catch((err) => setError(typeof err === 'string' ? err : 'Could not reach the server.'))
  }, [])

  return (
    <main>
      <header>
        <h1>Balatdle</h1>
        <p className="meta" aria-live="polite">
          {error ?? (puzzle ? `Puzzle #${puzzle.number} · ${puzzle.date}` : 'Loading today’s puzzle…')}
        </p>
      </header>

      {/* Guess submission is US-3; for now the field only holds what the player types. */}
      <form onSubmit={(e) => e.preventDefault()}>
        <label htmlFor="guess">Guess today’s joker</label>
        <input
          id="guess"
          value={guess}
          onChange={(e) => setGuess(e.target.value)}
          placeholder="Type a joker name"
          autoComplete="off"
          disabled={!puzzle}
        />
      </form>

      <section className="board" aria-label="Your guesses">
        <p className="empty">No guesses yet.</p>
      </section>
    </main>
  )
}
