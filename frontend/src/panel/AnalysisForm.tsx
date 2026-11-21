import { useEffect, useId, useState, type FormEvent } from 'react'
import { fetchCrops, type Crop } from '../api'
import { earliestIso } from '../dates'
import { todayIso } from '../useParcelReport'

interface Props {
  crop: string
  date: string
  busy: boolean
  onCropChange: (crop: string) => void
  onDateChange: (date: string) => void
  onSubmit: () => void
}

export function AnalysisForm({ crop, date, busy, onCropChange, onDateChange, onSubmit }: Props) {
  const cropId = useId()
  const dateId = useId()
  const [crops, setCrops] = useState<Crop[]>([])
  const today = todayIso()

  useEffect(() => {
    void fetchCrops().then(setCrops)
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
      <button type="submit" className="primary" disabled={busy || !crop}>
        {busy ? 'Analizuję…' : 'Analizuj działkę'}
      </button>
    </form>
  )
}
