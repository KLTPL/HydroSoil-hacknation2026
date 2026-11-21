import { useState, type FormEvent } from 'react'
import * as fmt from '../format'
import { errorMessage } from '../useParcelReport'
import { removeSaved, updateSaved, type SavedParcel } from './accountApi'
import { parcelLabel } from './labels'
import type { Account } from './useAccount'

interface Props {
  account: Account
  cropName: (id: string) => string
  onOpen: (saved: SavedParcel) => void
}

function Rename({ saved, onDone, onCancel }: { saved: SavedParcel; onDone: () => void; onCancel: () => void }) {
  const [name, setName] = useState(saved.name ?? '')
  const [error, setError] = useState<string | null>(null)

  async function submit(event: FormEvent) {
    event.preventDefault()
    try {
      await updateSaved(saved.id, { name })
      onDone()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <form
      className="rename"
      onSubmit={submit}
      onKeyDown={(event) => {
        if (event.key === 'Escape') onCancel()
      }}
    >
      <label className="visually-hidden" htmlFor={`rename-${saved.id}`}>
        Nowa nazwa działki {parcelLabel(saved)}
      </label>
      <input
        id={`rename-${saved.id}`}
        name="parcel-name"
        value={name}
        maxLength={60}
        placeholder="np. Pole za stodołą…"
        autoComplete="off"
        // Opened by the user's own click on "Zmień nazwę": typing can start right away.
        autoFocus
        onChange={(e) => setName(e.target.value)}
      />
      <button type="submit">Zapisz</button>
      <button type="button" className="quiet" onClick={onCancel}>
        Anuluj
      </button>
      <div aria-live="polite">{error && <p className="error">{error}</p>}</div>
    </form>
  )
}

export function MyParcels({ account, cropName, onOpen }: Props) {
  const [editing, setEditing] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  async function remove(saved: SavedParcel) {
    if (!window.confirm(`Usunąć „${parcelLabel(saved)}” z Moich działek? Archiwum raportów zostanie.`))
      return
    try {
      await removeSaved(saved.id)
      await account.refreshSaved()
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  if (account.saved.length === 0) {
    return (
      <p className="notice">
        Nie masz jeszcze zapisanych działek. Wybierz działkę i uprawę, a potem kliknij „Zapisz w
        Moich działkach” pod formularzem analizy.
      </p>
    )
  }

  return (
    <>
      <div aria-live="polite">{error && <p className="error">{error}</p>}</div>
      <ul className="saved-list">
        {account.saved.map((saved) => (
          <li key={saved.id} className="saved-item">
            <div className="saved-text">
              <strong>{parcelLabel(saved)}</strong>
              <span className="muted fine">
                {cropName(saved.crop)} · {fmt.ha(saved.area_ha)} · gm. {saved.commune}
                {saved.last_analysed_at
                  ? ` · analiza ${fmt.dateTime(saved.last_analysed_at)}`
                  : ' · jeszcze bez analizy'}
              </span>
            </div>
            <div className="saved-actions">
              <button
                type="button"
                className="chip"
                aria-label={`Otwórz analizę: ${parcelLabel(saved)}`}
                onClick={() => onOpen(saved)}
              >
                Otwórz analizę
              </button>
              <button
                type="button"
                className="quiet small"
                aria-expanded={editing === saved.id}
                aria-label={`Zmień nazwę: ${parcelLabel(saved)}`}
                onClick={() => setEditing(editing === saved.id ? null : saved.id)}
              >
                Zmień nazwę
              </button>
              <button
                type="button"
                className="quiet small"
                aria-label={`Usuń: ${parcelLabel(saved)}`}
                onClick={() => void remove(saved)}
              >
                Usuń
              </button>
            </div>
            {editing === saved.id && (
              <Rename
                saved={saved}
                onDone={() => {
                  setEditing(null)
                  void account.refreshSaved()
                }}
                onCancel={() => setEditing(null)}
              />
            )}
          </li>
        ))}
      </ul>
    </>
  )
}
