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

function Rename({ saved, onDone }: { saved: SavedParcel; onDone: () => void }) {
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
    <form className="rename" onSubmit={submit}>
      <label className="visually-hidden" htmlFor={`rename-${saved.id}`}>
        Nazwa działki
      </label>
      <input
        id={`rename-${saved.id}`}
        value={name}
        maxLength={60}
        placeholder="np. Pole za stodołą"
        autoFocus
        onChange={(e) => setName(e.target.value)}
      />
      <button type="submit">Zapisz</button>
      {error && <p className="error">{error}</p>}
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
      {error && <p className="error">{error}</p>}
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
              <button type="button" className="chip" onClick={() => onOpen(saved)}>
                Otwórz analizę
              </button>
              <button
                type="button"
                className="quiet small"
                aria-expanded={editing === saved.id}
                onClick={() => setEditing(editing === saved.id ? null : saved.id)}
              >
                Zmień nazwę
              </button>
              <button type="button" className="quiet small" onClick={() => void remove(saved)}>
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
              />
            )}
          </li>
        ))}
      </ul>
    </>
  )
}
