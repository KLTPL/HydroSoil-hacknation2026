import { useEffect, useState, type CSSProperties } from 'react'
import type { ModuleName, ModuleProgress, Parcel } from '../model'

const STEPS: { module: ModuleName; label: string; source: string }[] = [
  { module: 'water', label: 'Pogoda z 10 lat i woda w glebie', source: 'ERA5 · Open-Meteo' },
  { module: 'soil', label: 'Gleba i jej pojemność wodna', source: 'SoilGrids ISRIC' },
  { module: 'satellite', label: 'Stan roślin z satelity', source: 'Sentinel-2 · Copernicus' },
  { module: 'terrain', label: 'Rzeźba terenu i rowy', source: 'LIDAR GUGiK · OSM' },
  { module: 'land', label: 'Pokrycie terenu', source: 'ESA WorldCover' },
  { module: 'hydro', label: 'Ostrzeżenia hydrologiczne', source: 'IMGW-PIB' },
]

const seconds = new Intl.NumberFormat('pl-PL', { minimumFractionDigits: 1, maximumFractionDigits: 1 })

/** Live checklist of the data sources while the analysis runs (instead of a spinner). */
export function Progress({
  parcel,
  started,
  progress,
}: {
  parcel: Parcel
  started: number
  progress: ModuleProgress[]
}) {
  const [now, setNow] = useState(() => performance.now())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(performance.now()), 100)
    return () => window.clearInterval(timer)
  }, [])
  const done = new Map(progress.map((p) => [p.module, p]))
  const share = (done.size + 1) / (STEPS.length + 1)

  return (
    <section className="progress card" aria-label="Postęp analizy">
      <header className="progress-head">
        <div>
          <p className="eyebrow">Analizuję działkę {parcel.number}</p>
          <p className="progress-count">
            {done.size + 1} z {STEPS.length + 1} źródeł danych
          </p>
        </div>
        <span className="progress-time" aria-hidden="true">
          {seconds.format((now - started) / 1000)} s
        </span>
      </header>
      <div className="progress-bar" style={{ '--share': share } as CSSProperties} aria-hidden="true" />
      <ol className="progress-steps" aria-live="polite">
        <li className="step-ok">
          <span className="step-icon" aria-hidden="true" />
          <span className="step-text">
            <span className="step-label">Granice działki</span>
            <span className="step-fact">{parcel.region}, {parcel.area_ha.toFixed(1).replace('.', ',')} ha · ULDK GUGiK</span>
          </span>
        </li>
        {STEPS.map((step) => {
          const result = done.get(step.module)
          const state = !result ? 'wait' : result.status === 'ok' ? 'ok' : result.status
          return (
            <li key={step.module} className={`step-${state}`}>
              <span className="step-icon" aria-hidden="true" />
              <span className="step-text">
                <span className="step-label">{step.label}</span>
                <span className="step-fact">
                  {result ? result.fact : `pobieram… · ${step.source}`}
                </span>
              </span>
              {result && (
                <span className="step-time">
                  {result.live ? seconds.format(result.duration_ms / 1000) + ' s' : 'z pamięci'}
                </span>
              )}
            </li>
          )
        })}
      </ol>
    </section>
  )
}
