import { useId, useState, type FormEvent, type KeyboardEvent } from 'react'
import { searchParcels, type Parcel } from '../api'
import { plural } from '../format'
import { searchPlaces, type Place } from '../geocode'
import { errorMessage } from '../useParcelReport'
import { usePlaceSuggestions } from './usePlaceSuggestions'

type SearchState =
  | { status: 'idle' | 'loading' }
  | { status: 'error'; message: string }
  | { status: 'results'; parcels: Parcel[] }
  | { status: 'placed'; place: Place }

interface Props {
  /** A parcel is chosen: the label and the how-to hint give way to it. */
  compact: boolean
  onChoose: (parcel: Parcel) => void
  onPlace: (place: Place) => void
}

/** Full parcel ids ("040706_5.0016.51/1") are never place names. */
const PARCEL_ID = /^\d{6}_\d/

export function ParcelSearch({ compact, onChoose, onPlace }: Props) {
  const inputId = useId()
  const hintId = useId()
  const listId = useId()
  const [query, setQuery] = useState('')
  const [state, setState] = useState<SearchState>({ status: 'idle' })
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const suggestions = usePlaceSuggestions(query, !PARCEL_ID.test(query.trim()))
  const places = open && suggestions.status === 'done' ? suggestions.places : []
  const optionId = (index: number) => `${listId}-${index}`

  function goTo(place: Place) {
    onPlace(place)
    setQuery(place.label)
    setOpen(false)
    setState({ status: 'placed', place })
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    if (places[active]) return goTo(places[active])
    const q = query.trim()
    if (q.length < 2) return
    setOpen(false)
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
      // Not a parcel number: fly to the best matching town or address, as a map search does.
      const fresh = suggestions.status === 'done' && suggestions.query === q
      const [best] = fresh ? suggestions.places : await searchPlaces(q)
      if (best) goTo(best)
      else
        setState({
          status: 'error',
          message: 'Nie znaleziono działki ani miejscowości. Sprawdź pisownię.',
        })
    } catch (error) {
      setState({ status: 'error', message: errorMessage(error) })
    }
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === 'Escape' && open) {
      event.preventDefault()
      setOpen(false)
    } else if ((event.key === 'ArrowDown' || event.key === 'ArrowUp') && places.length) {
      event.preventDefault()
      // Cycles through the options and back to the typed text (-1).
      const step = event.key === 'ArrowDown' ? 1 : -1
      const slots = places.length + 1
      setActive(((active + 1 + step + slots) % slots) - 1)
    }
  }

  return (
    <form className="search" onSubmit={submit} role="search">
      <label htmlFor={inputId} className={compact ? 'visually-hidden' : undefined}>
        Działka, miejscowość lub adres
      </label>
      <div className="search-row">
        <input
          id={inputId}
          name="parcel"
          type="search"
          role="combobox"
          aria-autocomplete="list"
          aria-expanded={places.length > 0}
          aria-controls={listId}
          aria-activedescendant={places[active] ? optionId(active) : undefined}
          enterKeyHint="search"
          aria-describedby={hintId}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
            setActive(-1)
          }}
          onKeyDown={onKeyDown}
          onBlur={() => setOpen(false)}
          placeholder="np. Karczyn 51/1, Kruszwica, Kętrzyn Mazurska 5…"
          autoComplete="off"
          spellCheck={false}
        />
        <button type="submit" disabled={state.status === 'loading'}>
          {state.status === 'loading' ? 'Szukam…' : 'Szukaj'}
        </button>
      </div>
      <ul id={listId} role="listbox" className="search-suggestions" aria-label="Podpowiedzi miejsc" hidden={!places.length}>
        {places.map((p, index) => (
          <li
            key={p.id}
            id={optionId(index)}
            role="option"
            aria-selected={index === active}
            // Keeps focus in the input so its blur does not close the list before the click.
            onMouseDown={(e) => e.preventDefault()}
            onClick={() => goTo(p)}
          >
            <strong>{p.label}</strong>
            {p.area && <span className="muted"> · {p.area}</span>}
          </li>
        ))}
      </ul>
      <p id={hintId} className={compact ? 'visually-hidden' : 'muted'}>
        Nie znasz numeru? Wpisz miejscowość lub adres, a potem kliknij działkę na mapie. Możesz też
        użyć lokalizacji (◎).
      </p>
      <div aria-live="polite">
        {state.status === 'error' && <p className="error">{state.message}</p>}
        {open && suggestions.status === 'error' && <p className="error">{suggestions.message}</p>}
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
    </form>
  )
}
