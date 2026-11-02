import { useEffect, useState } from 'react'

// Anonymous player id kept in the browser, so guesses are stored against a player without an account.
function playerToken() {
  try {
    let token = localStorage.getItem('balatdle-token')
    if (!token) {
      token = crypto.randomUUID()
      localStorage.setItem('balatdle-token', token)
    }
    return token
  } catch {
    return crypto.randomUUID() // storage blocked: still playable, just not remembered
  }
}

async function getJson(url, options) {
  const res = await fetch(url, options)
  const body = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(body.error ?? 'Could not reach the server.')
  return body
}

export default function App() {
  const [token] = useState(playerToken)
  const [puzzle, setPuzzle] = useState(null)
  const [names, setNames] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [guess, setGuess] = useState('')
  const [guesses, setGuesses] = useState([])
  const [message, setMessage] = useState('')
  const [sending, setSending] = useState(false)

  useEffect(() => {
    Promise.all([getJson('/api/puzzle'), getJson('/api/jokers')])
      .then(([p, j]) => {
        setPuzzle(p)
        setNames(j.names)
      })
      .catch((err) => setLoadError(err.message))
  }, [])

  async function submit(e) {
    e.preventDefault()
    if (sending || !guess.trim()) return
    setSending(true)
    setMessage('')
    try {
      const saved = await getJson('/api/guess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, name: guess }),
      })
      setGuesses((prev) => [saved, ...prev])
      setGuess('')
    } catch (err) {
      setMessage(err.message)
    } finally {
      setSending(false)
    }
  }

  return (
    <main>
      <header>
        <h1>Balatdle</h1>
        <p className="meta">
          {loadError ?? (puzzle ? `Puzzle #${puzzle.number} · ${puzzle.date}` : 'Loading today’s puzzle…')}
        </p>
      </header>

      <form onSubmit={submit}>
        <label htmlFor="guess">Guess today’s joker</label>
        <input
          id="guess"
          list="joker-names"
          value={guess}
          onChange={(e) => setGuess(e.target.value)}
          placeholder="Type a joker name"
          autoComplete="off"
          disabled={!puzzle}
          aria-busy={sending}
        />
        <datalist id="joker-names">
          {names.map((name) => <option key={name} value={name} />)}
        </datalist>
        <p className="message" role="status">{message}</p>
      </form>

      {/* Colour feedback on each guess is US-4; for now the board lists what was guessed. */}
      <section className="board" aria-label="Your guesses">
        {guesses.length === 0 ? (
          <p className="empty">No guesses yet.</p>
        ) : (
          <ol reversed>
            {guesses.map((g) => (
              <li key={g.number}>
                <span className="number">#{g.number}</span> {g.name}
              </li>
            ))}
          </ol>
        )}
      </section>
    </main>
  )
}
