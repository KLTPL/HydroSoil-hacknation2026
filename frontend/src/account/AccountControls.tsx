import { useState } from 'react'
import type { Parcel } from '../model'
import { errorMessage } from '../useParcelReport'
import { saveParcel } from './accountApi'
import type { Account } from './useAccount'

/** Small, unobtrusive entry point in the panel header. */
export function AccountButton({ account, onOpen }: { account: Account; onOpen: () => void }) {
  if (account.state.status === 'checking') return null
  return (
    <button type="button" className="account-button no-print" onClick={onOpen}>
      {account.state.status === 'user' ? 'Moje działki' : 'Zaloguj się'}
    </button>
  )
}

interface SaveProps {
  account: Account
  parcel: Parcel
  crop: string
}

/** Saves the chosen parcel with its crop; shown only to logged-in users. */
export function SaveParcelButton({ account, parcel, crop }: SaveProps) {
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (account.state.status !== 'user') return null
  const saved = account.saved.some((s) => s.parcel_id === parcel.id)

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await saveParcel(parcel.id, crop)
      await account.refreshSaved()
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="save-parcel no-print" aria-live="polite">
      {saved ? (
        <p className="muted fine">Zapisana w Moich działkach</p>
      ) : (
        <button type="button" className="chip" disabled={busy || !crop} onClick={() => void save()}>
          {crop ? 'Zapisz w Moich działkach' : 'Wybierz uprawę, aby zapisać działkę'}
        </button>
      )}
      {error && <p className="error">{error}</p>}
    </div>
  )
}
