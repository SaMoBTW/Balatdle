import { useEffect, useMemo, useRef, useState } from 'react'

// Must match slug() in backend/fetch_sprites.py, which names the sprite files.
function slug(name) {
  return name.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '')
}

// Lowercase, accent-free text for matching, so "seance" finds Séance.
function fold(text) {
  return text.normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase()
}

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

const prefersReducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/* ---------- Pixel icons: drawn on a 7x7 grid so they match the pixel type ---------- */

const ICONS = {
  exact: ['......#', '.....##', '#...##.', '##.##..', '.###...', '..#....', '.......'],
  partial: ['.......', '.......', '.##....', '#..#..#', '....##.', '.......', '.......'],
  none: ['#.....#', '.#...#.', '..#.#..', '...#...', '..#.#..', '.#...#.', '#.....#'],
  higher: ['...#...', '..###..', '.#.#.#.', '...#...', '...#...', '...#...', '...#...'],
  lower: ['...#...', '...#...', '...#...', '...#...', '.#.#.#.', '..###..', '...#...'],
}

function PixelIcon({ name }) {
  return (
    <svg className="icon" viewBox="0 0 7 7" aria-hidden="true" shapeRendering="crispEdges">
      {ICONS[name].flatMap((row, y) =>
        [...row].map((cell, x) => (cell === '#' ? <rect key={`${x}-${y}`} x={x} y={y} width="1" height="1" /> : null)),
      )}
    </svg>
  )
}

/* ---------- Background: Balatro-style swirling paint, drawn small and scaled up ---------- */

const SWIRL = `
precision mediump float;
uniform vec2 res;
uniform float t;
void main() {
  vec2 uv = (gl_FragCoord.xy - 0.5 * res) / max(res.x, res.y);
  float r = length(uv);
  float a = atan(uv.y, uv.x) + t * 0.04 - r * 5.0;
  vec2 p = vec2(cos(a), sin(a)) * r * 7.0;
  for (int i = 0; i < 5; i++) {
    p += vec2(sin(p.y * 0.9 + t * 0.25), cos(p.x * 0.9 - t * 0.2)) * 0.55;
  }
  float v = sin(length(p) * 1.3) * 0.5 + 0.5;
  vec3 deep = vec3(0.055, 0.145, 0.118);
  vec3 felt = vec3(0.106, 0.271, 0.212);
  vec3 sheen = vec3(0.165, 0.384, 0.302);
  vec3 col = mix(deep, felt, smoothstep(0.25, 0.55, v));
  col = mix(col, sheen, smoothstep(0.78, 0.92, v));
  gl_FragColor = vec4(col, 1.0);
}`

function Swirl() {
  const canvasRef = useRef(null)

  useEffect(() => {
    const canvas = canvasRef.current
    const gl = canvas.getContext('webgl', { antialias: false, alpha: false })
    if (!gl) return // the CSS background colour shows instead

    const shader = (type, source) => {
      const s = gl.createShader(type)
      gl.shaderSource(s, source)
      gl.compileShader(s)
      return s
    }
    const program = gl.createProgram()
    gl.attachShader(program, shader(gl.VERTEX_SHADER, 'attribute vec2 p; void main() { gl_Position = vec4(p, 0.0, 1.0); }'))
    gl.attachShader(program, shader(gl.FRAGMENT_SHADER, SWIRL))
    gl.linkProgram(program)
    gl.useProgram(program)
    gl.bindBuffer(gl.ARRAY_BUFFER, gl.createBuffer())
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW)
    const pos = gl.getAttribLocation(program, 'p')
    gl.enableVertexAttribArray(pos)
    gl.vertexAttribPointer(pos, 2, gl.FLOAT, false, 0, 0)
    const res = gl.getUniformLocation(program, 'res')
    const time = gl.getUniformLocation(program, 't')

    // A quarter-resolution canvas, scaled up with crisp pixels, keeps the GPU cost tiny.
    const resize = () => {
      canvas.width = Math.ceil(window.innerWidth / 4)
      canvas.height = Math.ceil(window.innerHeight / 4)
      gl.viewport(0, 0, canvas.width, canvas.height)
    }
    const draw = (seconds) => {
      gl.uniform2f(res, canvas.width, canvas.height)
      gl.uniform1f(time, seconds)
      gl.drawArrays(gl.TRIANGLES, 0, 3)
    }
    resize()
    window.addEventListener('resize', resize)

    if (prefersReducedMotion()) {
      draw(20) // one still frame, no movement
      const redraw = () => draw(20)
      window.addEventListener('resize', redraw)
      return () => {
        window.removeEventListener('resize', resize)
        window.removeEventListener('resize', redraw)
      }
    }

    let frame
    let last = 0
    const loop = (now) => {
      frame = requestAnimationFrame(loop)
      if (now - last < 1000 / 30) return // 30 fps is plenty for slow paint
      last = now
      draw(now / 1000)
    }
    frame = requestAnimationFrame(loop)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', resize)
    }
  }, [])

  return <canvas ref={canvasRef} className="swirl" aria-hidden="true" />
}

/* ---------- Joker sprite ---------- */

function Sprite({ name, size = 'card' }) {
  return (
    <img
      className={`sprite sprite-${size}`}
      src={`/jokers/${slug(name)}.png`}
      alt=""
      width={size === 'thumb' ? 45 : 71}
      height={size === 'thumb' ? 60 : 95}
      loading="lazy"
      decoding="async"
    />
  )
}

/* ---------- Guess field with pictured suggestions (ARIA combobox) ---------- */

function JokerPicker({ jokers, guessed, left, disabled, onGuess }) {
  const [text, setText] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const [sending, setSending] = useState(false)
  const listRef = useRef(null)

  const matches = useMemo(() => {
    const q = fold(text.trim())
    if (!q) return []
    const taken = new Set(guessed)
    return jokers
      .filter((j) => !taken.has(j.name) && fold(j.name).includes(q))
      .sort((a, b) => Number(!fold(a.name).startsWith(q)) - Number(!fold(b.name).startsWith(q)))
      .slice(0, 8)
  }, [text, jokers, guessed])

  const expanded = open && matches.length > 0

  useEffect(() => {
    listRef.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [active])

  async function send(name) {
    if (sending || !name.trim()) return
    setSending(true)
    setOpen(false)
    const ok = await onGuess(name)
    setSending(false)
    if (ok) setText('')
  }

  function onKeyDown(e) {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActive((i) => (expanded ? (i + 1) % matches.length : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => (expanded ? (i - 1 + matches.length) % matches.length : 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      send(expanded ? matches[active].name : text)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="picker">
      <div className="picker-head">
        <label htmlFor="guess">Guess today’s joker</label>
        {left !== null && (
          <span className={`left${left <= 2 ? ' low' : ''}`}>
            {left} {left === 1 ? 'guess' : 'guesses'} left
          </span>
        )}
      </div>
      <div className="field">
        <input
          id="guess"
          role="combobox"
          aria-expanded={expanded}
          aria-controls="joker-options"
          aria-autocomplete="list"
          aria-activedescendant={expanded ? `joker-option-${active}` : undefined}
          aria-busy={sending}
          value={text}
          onChange={(e) => {
            setText(e.target.value)
            setActive(0)
            setOpen(true)
          }}
          onKeyDown={onKeyDown}
          onBlur={() => setOpen(false)}
          onFocus={() => setOpen(true)}
          placeholder="Type a joker name"
          autoComplete="off"
          spellCheck="false"
          disabled={disabled}
        />
        <button type="button" className="play" onClick={() => send(expanded ? matches[active].name : text)} disabled={disabled || !text.trim()}>
          Guess
        </button>
      </div>
      <ul id="joker-options" role="listbox" aria-label="Matching jokers" ref={listRef} hidden={!expanded}>
        {matches.map((joker, i) => (
          <li
            key={joker.name}
            id={`joker-option-${i}`}
            role="option"
            aria-selected={i === active}
            onMouseDown={(e) => e.preventDefault()} // keep focus in the field
            onMouseEnter={() => setActive(i)}
            onClick={() => send(joker.name)}
          >
            <Sprite name={joker.name} size="thumb" />
            <span className="option-text">
              <span className="option-name">
                {joker.name}
                <span className={`rarity ${joker.rarity.toLowerCase()}`}>{joker.rarity}</span>
              </span>
              <span className="effect">{joker.effect.replace(/\s*\(Currently[^)]*\)/, '')}</span>
            </span>
          </li>
        ))}
      </ul>
      <p className="sr-only" role="status">
        {expanded ? `${matches.length} matching ${matches.length === 1 ? 'joker' : 'jokers'}` : ''}
      </p>
    </div>
  )
}

/* ---------- One guessed joker ---------- */

const LABELS = {
  rarity: 'Rarity',
  cost: 'Cost',
  effect_type: 'Type',
  activation: 'Activation',
  scales: 'Scales',
  unlock_method: 'Unlock',
}
const SPOKEN = { exact: 'exact match', partial: 'close', none: 'no match' }
const SPOKEN_ARROWS = { higher: 'answer costs more', lower: 'answer costs less' }

function shown(f) {
  if (f.attribute === 'cost') return `$${f.value}`
  if (f.attribute === 'scales') return f.value ? 'Yes' : 'No'
  return f.value
}

// Colour, a drawn icon and spoken text on every tile, so colour is never the only signal.
function GuessCard({ guess }) {
  return (
    <li className={`guess${guess.fresh ? ' fresh' : ''}`}>
      <Sprite name={guess.name} />
      <div className="guess-body">
        <h2>
          <span className="number">#{guess.number}</span> {guess.name}
        </h2>
        <dl className="tiles">
          {guess.feedback.map((f, i) => (
            <div key={f.attribute} className={`tile ${f.match}`} style={{ '--i': i }}>
              <dt>{LABELS[f.attribute]}</dt>
              <dd>
                <span className="value">{shown(f)}</span>
                <span className="marks">
                  <PixelIcon name={f.match} />
                  {f.direction && <PixelIcon name={f.direction} />}
                </span>
                <span className="sr-only">
                  , {SPOKEN[f.match]}
                  {f.direction && `, ${SPOKEN_ARROWS[f.direction]}`}
                </span>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </li>
  )
}

/* ---------- Page ---------- */

export default function App() {
  const [token] = useState(playerToken)
  const [puzzle, setPuzzle] = useState(null)
  const [jokers, setJokers] = useState([])
  const [loadError, setLoadError] = useState(null)
  const [guesses, setGuesses] = useState([])
  const [message, setMessage] = useState('')
  const win = guesses.find((g) => g.solved)
  const loss = guesses.find((g) => g.lost)
  const resultRef = useRef(null)
  const left = puzzle ? Math.max(puzzle.max_guesses - guesses.length, 0) : null

  useEffect(() => {
    const progress = getJson('/api/progress', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token }),
    })
    Promise.all([getJson('/api/puzzle'), getJson('/api/jokers'), progress])
      .then(([p, j, saved]) => {
        setPuzzle(p)
        setJokers(j.jokers)
        setGuesses(saved.guesses.slice().reverse()) // newest first, as new guesses are added
      })
      .catch((err) => setLoadError(err.message))
  }, [token])

  // Disabling the field drops keyboard focus, so move it to the result instead.
  useEffect(() => {
    if (win || loss) resultRef.current?.focus()
  }, [win, loss])

  async function guess(name) {
    setMessage('')
    try {
      const saved = await getJson('/api/guess', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, name }),
      })
      setGuesses((prev) => [{ ...saved, fresh: !prefersReducedMotion() }, ...prev])
      return true
    } catch (err) {
      setMessage(err.message)
      return false
    }
  }

  const day = puzzle && new Date(`${puzzle.date}T00:00:00Z`).toLocaleDateString(undefined, { month: 'long', day: 'numeric', timeZone: 'UTC' })

  return (
    <>
      <Swirl />
      <main>
        <header>
          <h1>Balatdle</h1>
          <p className="meta">{loadError ?? (puzzle ? `Puzzle #${puzzle.number} · ${day}` : 'Loading today’s puzzle…')}</p>
        </header>

        <JokerPicker
          jokers={jokers}
          guessed={guesses.map((g) => g.name)}
          left={win || loss ? null : left}
          disabled={!puzzle || Boolean(win || loss)}
          onGuess={guess}
        />
        <p className="message" role="alert">
          {message}
        </p>

        {win && (
          <section className="result win" ref={resultRef} tabIndex={-1} aria-labelledby="result-title">
            <Sprite name={win.name} />
            <div>
              <h2 id="result-title">Solved</h2>
              <p>
                Today’s joker was <strong>{win.name}</strong>, and you found it in {win.number}{' '}
                {win.number === 1 ? 'guess' : 'guesses'}.
              </p>
            </div>
          </section>
        )}

        {loss && (
          <section className="result loss" ref={resultRef} tabIndex={-1} aria-labelledby="result-title">
            <Sprite name={loss.answer} />
            <div>
              <h2 id="result-title">Out of guesses</h2>
              <p>
                Today’s joker was <strong>{loss.answer}</strong>. A new puzzle comes out at midnight UTC.
              </p>
            </div>
          </section>
        )}

        <section className="board" aria-label="Your guesses">
          {guesses.length === 0 ? (
            <p className="empty">Your guesses show up here, with a clue on each of the six attributes.</p>
          ) : (
            <>
              <ul className="legend" aria-label="What the marks mean">
                <li><PixelIcon name="exact" /> exact</li>
                <li><PixelIcon name="partial" /> close</li>
                <li><PixelIcon name="none" /> no match</li>
                <li><PixelIcon name="higher" /><PixelIcon name="lower" /> answer costs more or less</li>
              </ul>
              <ol className="guesses">
                {guesses.map((g) => <GuessCard key={g.number} guess={g} />)}
              </ol>
            </>
          )}
        </section>

        <footer>
          Joker names and art are from <cite>Balatro</cite> by LocalThunk, published by Playstack. Sprites via the{' '}
          <a href="https://balatrowiki.org/w/Jokers">Balatro Wiki</a>. Balatdle is a fan-made class project with no
          connection to either.
        </footer>
      </main>
    </>
  )
}
