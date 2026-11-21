import { useId, useState, type FormEvent } from 'react'
import { searchParcels, type Parcel } from '../api'
import { errorMessage } from '../useParcelReport'

type SearchState =
  | { status: 'idle' | 'loading' }
  | { status: 'error'; message: string }
  | { status: 'results'; parcels: Parcel[] }

export function ParcelSearch({ onChoose }: { onChoose: (parcel: Parcel) => void }) {
  const inputId = useId()
  const hintId = useId()
  const [query, setQuery] = useState('')
  const [state, setState] = useState<SearchState>({ status: 'idle' })

  async function submit(event: FormEvent) {
    event.preventDefault()
    const q = query.trim()
    if (q.length < 2) return
    setState({ status: 'loading' })
    try {
      const parcels = await searchParcels(q)
      if (parcels.length === 1) {
        onChoose(parcels[0])
        setState({ status: 'idle' })
      } else if (parcels.length === 0) {
        setState({ status: 'error', message: 'Nie znaleziono działki. Sprawdź numer.' })
      } else {
        setState({ status: 'results', parcels })
      }
    } catch (error) {
      setState({ status: 'error', message: errorMessage(error) })
    }
  }

  return (
    <form className="search" onSubmit={submit} role="search">
      <label htmlFor={inputId}>Numer działki</label>
      <div className="search-row">
        <input
          id={inputId}
          aria-describedby={hintId}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="np. 040706_5.0016.51/1 lub Karczyn 51/1"
          autoComplete="off"
          spellCheck={false}
        />
        <button type="submit" disabled={state.status === 'loading'}>
          {state.status === 'loading' ? 'Szukam…' : 'Szukaj'}
        </button>
      </div>
      <p id={hintId} className="muted">
        Pełny identyfikator albo nazwa obrębu i numer. Możesz też kliknąć działkę na mapie lub
        użyć lokalizacji (◎).
      </p>
      {state.status === 'error' && <p className="error">{state.message}</p>}
      {state.status === 'results' && (
        <ul className="search-results" aria-label="Znalezione działki">
          {state.parcels.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => {
                  onChoose(p)
                  setState({ status: 'idle' })
                }}
              >
                <strong>{p.number}</strong> · {p.region}, gm. {p.commune} ({p.voivodeship})
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  )
}
