import type { Diagnosis } from '../api'
import * as fmt from '../format'

const LEVEL_LABEL = {
  none: 'Woda: bez niedoboru',
  watch: 'Woda: uwaga',
  moderate: 'Woda: niedobór',
  severe: 'Woda: silny niedobór',
} as const

const CONFIDENCE_LABEL = {
  high: 'wysoka (źródła są zgodne)',
  medium: 'średnia (część danych brakuje lub źródła się różnią)',
  low: 'niska (brak kluczowych danych)',
} as const

export function DiagnosisSection({ diagnosis }: { diagnosis: Diagnosis }) {
  const maxMm = Math.max(1, ...diagnosis.causes.map((c) => c.amount_mm ?? 0))
  return (
    <section className="report-section" aria-labelledby="diagnosis-heading">
      <h3 id="diagnosis-heading">Ocena sytuacji wodnej</h3>
      <p className={`level level-${diagnosis.level}`}>{LEVEL_LABEL[diagnosis.level]}</p>
      <p className="headline">{diagnosis.headline}</p>
      {diagnosis.evidence.length > 0 && (
        <ul className="evidence">
          {diagnosis.evidence.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      <p className="muted">Wiarygodność oceny: {CONFIDENCE_LABEL[diagnosis.confidence]}</p>

      {diagnosis.causes.length > 0 && (
        <>
          <h4>Dlaczego brakuje wody</h4>
          <ol className="causes">
            {diagnosis.causes.map((cause) => (
              <li key={cause.key}>
                <div className="cause-head">
                  <span className="cause-title">{cause.title}</span>
                  {cause.amount_mm !== null && (
                    <span className="cause-mm">{fmt.mm(cause.amount_mm)}</span>
                  )}
                </div>
                {cause.amount_mm !== null && (
                  <span
                    className="cause-bar"
                    style={{ width: `${(100 * cause.amount_mm) / maxMm}%` }}
                    aria-hidden="true"
                  />
                )}
                <p className="muted">{cause.detail}</p>
              </li>
            ))}
          </ol>
        </>
      )}
    </section>
  )
}

export function LimitationsSection({ diagnosis }: { diagnosis: Diagnosis }) {
  return (
    <section className="report-section" aria-labelledby="limits-heading">
      <h3 id="limits-heading">Ograniczenia i brakujące dane</h3>
      {diagnosis.missing_data.length > 0 && (
        <ul className="missing">
          {diagnosis.missing_data.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      <ul className="muted">
        {diagnosis.limitations.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </section>
  )
}
