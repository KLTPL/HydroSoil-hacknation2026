import { useId } from 'react'
import * as fmt from '../format'
import type { Diagnosis, SourceSignal, WaterBalance } from '../model'
import { useCountUp } from '../useCountUp'
import { LEVEL } from './levels'

const CONFIDENCE = {
  high: 'Pewność oceny: wysoka. Źródła są zgodne.',
  medium: 'Pewność oceny: średnia. Część danych brakuje albo źródła się różnią.',
  low: 'Pewność oceny: niska. Brakuje kluczowych danych.',
} as const

const VERDICT = {
  dry: 'suszej niż zwykle',
  normal: 'typowo',
  wet: 'wilgotniej niż zwykle',
  missing: 'brak danych',
} as const

/** Root-zone water as a tank: level now, the crop's stress line and the usual level. */
function SoilTank({ pct, threshold, normal }: { pct: number; threshold: number; normal: number }) {
  const clip = useId()
  const top = 8
  const height = 124
  const level = useCountUp(pct)
  const y = (p: number) => top + height * (1 - Math.min(100, Math.max(0, p)) / 100)
  const surface = y(level)
  return (
    <svg className="tank" viewBox="0 0 84 140" role="img" aria-label={`Woda w glebie: ${fmt.pct(pct)}`}>
      <defs>
        <clipPath id={clip}>
          <rect x="8" y={top} width="68" height={height} rx="16" />
        </clipPath>
      </defs>
      <rect className="tank-body" x="8" y={top} width="68" height={height} rx="16" />
      <g clipPath={`url(#${clip})`}>
        <rect className="tank-stress" x="8" y={y(threshold)} width="68" height={top + height - y(threshold)} />
        <path
          className="tank-water"
          d={`M8 ${surface} q8.5 -3 17 0 t17 0 t17 0 t17 0 V${top + height} H8 Z`}
        />
      </g>
      <line className="tank-threshold" x1="2" x2="82" y1={y(threshold)} y2={y(threshold)} />
      <path className="tank-normal" d={`M76 ${y(normal)} l7 -4 v8 z`} />
      <rect className="tank-rim" x="8" y={top} width="68" height={height} rx="16" />
    </svg>
  )
}

// The IUNG criterion is a threshold, not a comparison with earlier years.
const CRITERION: Record<SourceSignal['verdict'], string> = {
  dry: 'susza',
  normal: 'bez suszy',
  wet: 'bez suszy',
  missing: 'brak danych',
}

function SourceVotes({ signals }: { signals: SourceSignal[] }) {
  return (
    <ul className="votes" aria-label="Co mówią źródła danych na tle 10 lat">
      {signals.map((s) => (
        <li key={s.key} className={`vote vote-${s.verdict}`}>
          <span className="vote-dot" aria-hidden="true" />
          <span className="vote-source">{s.source}</span>
          <span className="vote-verdict">
            {s.key === 'smsr' ? CRITERION[s.verdict] : VERDICT[s.verdict]}
          </span>
          {s.verdict !== 'missing' && (
            <span className="vote-detail">
              {s.value}
              {s.note && ` · ${s.note}`}
            </span>
          )}
        </li>
      ))}
    </ul>
  )
}

export function Verdict({ diagnosis, water }: { diagnosis: Diagnosis; water: WaterBalance | null }) {
  const level = LEVEL[diagnosis.level]
  const pct = useCountUp(water?.available_pct.value ?? 0)
  return (
    <section className={`verdict tone-${level.tone}`} aria-labelledby="verdict-heading">
      {diagnosis.warnings.map((warning) => (
        <p key={warning} className="warning" role="alert">
          {warning}
        </p>
      ))}
      <p className="eyebrow">1 · Ocena sytuacji wodnej</p>
      <h3 id="verdict-heading" className="verdict-level">
        <span className="level-dot" aria-hidden="true" />
        {level.label}
      </h3>
      {water && diagnosis.stress_threshold_pct !== null && (
        <div className="verdict-gauge">
          <SoilTank
            pct={water.available_pct.value}
            threshold={diagnosis.stress_threshold_pct}
            normal={water.available_pct.normal}
          />
          <div className="gauge-text">
            <p className="gauge-value">
              {Math.round(pct)}
              <span> %</span>
            </p>
            <p className="gauge-caption">
              {water.in_season ? 'wody dostępnej dla roślin w strefie korzeni' : 'zapasu wody w glebie'}
            </p>
            <ul className="gauge-key">
              <li className="key-threshold">stres uprawy poniżej {fmt.pct(diagnosis.stress_threshold_pct)}</li>
              <li className="key-normal">zwykle tego dnia {fmt.pct(water.available_pct.normal)}</li>
            </ul>
          </div>
        </div>
      )}
      <p className="verdict-headline">{diagnosis.headline}</p>
      {diagnosis.signals.length > 0 && <SourceVotes signals={diagnosis.signals} />}
      <p className="confidence">{CONFIDENCE[diagnosis.confidence]}</p>
    </section>
  )
}
