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
  onCropChange: (crop: string) => void
  onDateChange: (date: string) => void
  onSubmit: () => void
}

export function AnalysisForm({ crop, date, busy, current, onCropChange, onDateChange, onSubmit }: Props) {
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
    <form className="analysis-form" onSubmit={submit}>
      <div className="field">
        <label htmlFor={cropId}>Uprawa na działce</label>
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
        <label htmlFor={dateId}>Data analizy</label>
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
      <button type="submit" className={current ? 'primary is-current' : 'primary'} disabled={busy || current}>
        {busy ? 'Analizuję…' : current ? '✓ Raport poniżej jest aktualny' : 'Analizuj działkę'}
      </button>
    </form>
  )
}
