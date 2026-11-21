import { useId } from 'react'
import * as fmt from '../format'
import type { RetentionAnalysis } from '../model'

export type BaseLayer = 'photo' | 'relief'

const OPTIONS: { value: BaseLayer; label: string; hint: string }[] = [
  { value: 'photo', label: 'Zdjęcie', hint: 'Ortofotomapa GUGiK' },
  { value: 'relief', label: 'Rzeźba terenu', hint: 'Model terenu LIDAR: niecki i spływ wody' },
]

/** Segmented control: orthophoto or the LIDAR micro-relief the analysis sees. */
export function LayerSwitch({
  value,
  onChange,
  hasRelief,
}: {
  value: BaseLayer
  onChange: (value: BaseLayer) => void
  hasRelief: boolean
}) {
  const name = useId()
  if (!hasRelief) return null
  return (
    <fieldset className="glass segmented layer-switch">
      <legend className="visually-hidden">Podkład mapy</legend>
      {OPTIONS.map((o) => (
        <label key={o.value} title={o.hint}>
          <input
            type="radio"
            name={name}
            value={o.value}
            checked={value === o.value}
            onChange={() => onChange(o.value)}
          />
          <span>{o.label}</span>
        </label>
      ))}
    </fieldset>
  )
}

export function Legend({ terrain, base }: { terrain: RetentionAnalysis; base: BaseLayer }) {
  const weirs = terrain.ditches.reduce((n, d) => n + d.weir_count, 0)
  return (
    <aside className="glass legend" aria-label="Legenda mapy">
      <ul>
        <li>
          <span className="swatch swatch-parcel" /> Twoja działka
        </li>
        {terrain.sites.length > 0 && (
          <li>
            <span className="swatch swatch-site" /> Miejsca na wodę ({terrain.sites.length})
          </li>
        )}
        {terrain.ditches.length > 0 && (
          <li>
            <span className="swatch swatch-ditch" /> Rowy ({terrain.ditches.length})
          </li>
        )}
        {weirs > 0 && (
          <li>
            <span className="swatch swatch-weir" /> Proponowane zastawki ({weirs})
          </li>
        )}
        {base === 'relief' && terrain.flow.length > 0 && (
          <li>
            <span className="swatch swatch-flow" /> Drogi spływu wody
          </li>
        )}
      </ul>
      {base === 'relief' && terrain.relief && (
        <div className="relief-scale">
          <span className="relief-ramp" aria-hidden="true" />
          <span className="relief-labels">
            <span>niżej, zbiera wodę</span>
            <span>wyżej, schnie</span>
          </span>
          <span className="muted">
            ±{fmt.num(terrain.relief.spread_m * 100)} cm względem otoczenia · LIDAR GUGiK
          </span>
        </div>
      )}
    </aside>
  )
}
