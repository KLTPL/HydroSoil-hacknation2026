import { useEffect, useId, useState, type FormEvent } from 'react'
import { fetchCrops, type Crop } from '../api'
import { earliestIso } from '../dates'
import { errorMessage, todayIso } from '../useParcelReport'

interface Props {
  crop: string
  date: string
  busy: boolean
  /** The report below is for exactly this crop and date: nothing to rerun. */
  current: boolean
  /** A report is shown or running: one row without labels, the button only when needed. */
  compact: boolean
  onCropChange: (crop: string) => void
  onDateChange: (date: string) => void
  onSubmit: () => void
}

export function AnalysisForm({ crop, date, busy, current, compact, onCropChange, onDateChange, onSubmit }: Props) {
  const cropId = useId()
  const dateId = useId()
  const [crops, setCrops] = useState<Crop[]>([])
  const [cropsError, setCropsError] = useState<string | null>(null)
  const today = todayIso()

  useEffect(() => {
    fetchCrops().then(setCrops, (err: unknown) =>
      setCropsError(`Nie udało się wczytać listy upraw. ${errorMessage(err)}`),
    )
  }, [])

  function submit(event: FormEvent) {
    event.preventDefault()
    onSubmit()
  }

  return (
    <form className={compact ? 'analysis-form compact' : 'analysis-form'} onSubmit={submit}>
      <div className="field">
        <label htmlFor={cropId} className={compact ? 'visually-hidden' : undefined}>
          Uprawa na działce
        </label>
        <select id={cropId} value={crop} required onChange={(e) => onCropChange(e.target.value)}>
          <option value="" disabled>
            Wybierz uprawę…
          </option>
          {crops.map((c) => (
            <option key={c.id} value={c.id}>
              {c.name}
            </option>
          ))}
        </select>
        {cropsError && <p className="error fine" role="alert">{cropsError}</p>}
      </div>
      <div className="field">
        <label htmlFor={dateId} className={compact ? 'visually-hidden' : undefined}>
          Data analizy
        </label>
        <input
          id={dateId}
          type="date"
          value={date}
          min={earliestIso(today)}
          max={today}
          required
          onChange={(e) => onDateChange(e.target.value)}
        />
      </div>
      {!current && (
        <button type="submit" className="primary" disabled={busy}>
          {busy ? 'Analizuję…' : compact ? 'Analizuj ponownie' : 'Analizuj działkę'}
        </button>
      )}
    </form>
  )
}
