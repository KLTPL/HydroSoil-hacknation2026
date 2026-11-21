import { useId, useState, type FormEvent } from 'react'
import { searchParcels, type Parcel } from '../api'
import { plural } from '../format'
import { searchPlaces, type Place } from '../geocode'
import { errorMessage } from '../useParcelReport'

type SearchState =
  | { status: 'idle' | 'loading' }
  | { status: 'error'; message: string }
  | { status: 'results'; parcels: Parcel[] }
  | { status: 'places'; places: Place[] }
  | { status: 'placed'; place: Place }

interface Props {
  onChoose: (parcel: Parcel) => void
  onPlace: (place: Place) => void
}

export function ParcelSearch({ onChoose, onPlace }: Props) {
  const inputId = useId()
  const hintId = useId()
  const [query, setQuery] = useState('')
  const [state, setState] = useState<SearchState>({ status: 'idle' })

  function goTo(place: Place) {
    onPlace(place)
    setState({ status: 'placed', place })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    const q = query.trim()
    if (q.length < 2) return
    setState({ status: 'loading' })
    try {
      // A parcel number always has a digit; a bare town name skips the parcel lookup.
      const parcels = /\d/.test(q) ? await searchParcels(q) : []
      if (parcels.length === 1) {
        onChoose(parcels[0])
        setState({ status: 'idle' })
        return
      }
      if (parcels.length > 1) {
        setState({ status: 'results', parcels })
        return
      }
      // Not a parcel number: treat it as a town or address and fly the map there.
      const places = await searchPlaces(q)
      if (places.length === 1) goTo(places[0])
      else if (places.length > 1) setState({ status: 'places', places })
      else
        setState({
          status: 'error',
          message: 'Nie znaleziono działki ani miejscowości. Sprawdź pisownię.',
        })
    } catch (error) {
      setState({ status: 'error', message: errorMessage(error) })
    }
  }

  return (
    <form className="search" onSubmit={submit} role="search">
      <label htmlFor={inputId}>Działka, miejscowość lub adres</label>
      <div className="search-row">
        <input
          id={inputId}
          name="parcel"
          type="search"
          enterKeyHint="search"
          aria-describedby={hintId}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="np. Karczyn 51/1, Kruszwica, Karczyn 5…"
          autoComplete="off"
          spellCheck={false}
        />
        <button type="submit" disabled={state.status === 'loading'}>
          {state.status === 'loading' ? 'Szukam…' : 'Szukaj'}
        </button>
      </div>
      <p id={hintId} className="muted">
        Nie znasz numeru? Wpisz miejscowość lub adres, a potem kliknij działkę na mapie. Możesz też
        użyć lokalizacji (◎).
      </p>
      <div aria-live="polite">
        {state.status === 'error' && <p className="error">{state.message}</p>}
        {state.status === 'placed' && (
          <p className="search-placed">
            Mapa pokazuje: <strong>{state.place.label}</strong>. Kliknij swoją działkę na mapie.
          </p>
        )}
        {state.status === 'results' && (
          <p className="visually-hidden">
            Znaleziono {state.parcels.length}{' '}
            {plural(state.parcels.length, 'działkę', 'działki', 'działek')}. Wybierz jedną z listy.
          </p>
        )}
        {state.status === 'places' && (
          <p className="visually-hidden">
            Znaleziono {state.places.length}{' '}
            {plural(state.places.length, 'miejsce', 'miejsca', 'miejsc')}. Wybierz jedno z listy.
          </p>
        )}
      </div>
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
      {state.status === 'places' && (
        <ul className="search-results" aria-label="Znalezione miejscowości">
          {state.places.map((p) => (
            <li key={`${p.lon},${p.lat}`}>
              <button type="button" onClick={() => goTo(p)}>
                <strong>{p.label}</strong> · {p.area}
              </button>
            </li>
          ))}
        </ul>
      )}
    </form>
  )
}
