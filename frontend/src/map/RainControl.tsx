import type { Map as MapLibreMap } from 'maplibre-gl'
import { useEffect, useId, useRef, useState } from 'react'
import * as fmt from '../format'
import type { Range, RetentionAnalysis } from '../model'
import { FlowAnimation, RAIN_MS, type RainFrame } from './FlowAnimation'
import { FADED, SELECTED, SITES_FILL_LAYER } from './style'

type Mode = 'today' | 'plan'
type Phase = 'idle' | 'raining' | 'done'

const reducedMotion = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches
const ease = (t: number) => 1 - (1 - t) ** 3

function scale({ low, high }: Range, t: number): Range {
  return { low: low * t, high: high * t }
}

/** During the storm the hollows fill up: shallow puddles today, full ponds with the plan. */
function paintSites(map: MapLibreMap, phase: Phase, mode: Mode, fill: number) {
  const full = mode === 'plan' ? 0.92 : 0.4
  const filled = phase === 'idle' ? 0.55 : 0.04 + (full - 0.04) * fill
  map.setPaintProperty(SITES_FILL_LAYER, 'fill-opacity', ['case', FADED, 0.12, SELECTED, 0.95, filled])
  map.setPaintProperty('weirs', 'circle-radius', phase !== 'idle' && mode === 'plan' ? 9 : 6)
}

interface Props {
  map: MapLibreMap
  terrain: RetentionAnalysis
  areaHa: number
  onRainingChange: (raining: boolean) => void
}

/** "Puść ulewę": the design storm runs over the LIDAR flow network, with the volumes. */
export function RainControl({ map, terrain, areaHa, onRainingChange }: Props) {
  const [mode, setMode] = useState<Mode>('plan')
  const [phase, setPhase] = useState<Phase>('idle')
  const [frame, setFrame] = useState<RainFrame>({ elapsed: 0, progress: 0, done: false })
  const animation = useRef<FlowAnimation | null>(null)
  const lastFrame = useRef(0)
  const name = useId()

  useEffect(() => {
    const instance = new FlowAnimation(map, terrain.flow, (next) => {
      // React only needs ~12 updates per second for the counters.
      if (!next.done && next.elapsed - lastFrame.current < 80) return
      lastFrame.current = next.elapsed
      setFrame(next)
      if (next.done) setPhase('done')
    })
    animation.current = instance
    return () => {
      instance.destroy()
      animation.current = null
      setPhase('idle')
    }
  }, [map, terrain])

  useEffect(() => {
    onRainingChange(phase !== 'idle')
  }, [phase, onRainingChange])

  function play() {
    lastFrame.current = 0
    if (reducedMotion()) {
      setFrame({ elapsed: RAIN_MS, progress: 1, done: true })
      setPhase('done')
      return
    }
    setFrame({ elapsed: 0, progress: 0, done: false })
    setPhase('raining')
    animation.current?.play()
  }

  function stop() {
    animation.current?.stop()
    setPhase('idle')
  }

  const rain = terrain.assumptions.design_rain_mm
  const coeff = terrain.assumptions.runoff_coeff
  const fallen = areaHa * 10 * rain
  const weirs = terrain.ditches.reduce((sum, d) => sum + d.channel_m3, 0)
  const sites = terrain.summary.retained_m3
  const kept = { low: sites.low + weirs, high: sites.high + weirs }
  // Idle shows the totals; a running storm counts them up as the water arrives.
  const rainT = phase === 'raining' ? ease(Math.min(1, frame.elapsed / RAIN_MS)) : 1
  const flowT = phase === 'raining' ? ease(frame.progress) : 1
  useEffect(() => {
    paintSites(map, phase, mode, flowT)
  }, [map, phase, mode, flowT])

  return (
    <section className={`glass rain-control phase-${phase}`} aria-labelledby={`${name}-title`}>
      <header>
        <h2 id={`${name}-title`}>Ulewa {rain} mm na Twojej działce</h2>
        <fieldset className="segmented small">
          <legend className="visually-hidden">Wariant</legend>
          {(['today', 'plan'] as const).map((m) => (
            <label key={m}>
              <input
                type="radio"
                name={name}
                checked={mode === m}
                onChange={() => setMode(m)}
              />
              <span>{m === 'today' ? 'Dziś' : 'Z planem'}</span>
            </label>
          ))}
        </fieldset>
      </header>

      <dl className="rain-stats" aria-live="off">
        <div>
          <dt>Spada deszczu</dt>
          <dd>{fmt.m3(fallen * rainT)}</dd>
        </div>
        <div>
          <dt>Spływa po powierzchni</dt>
          <dd className="runoff">{fmt.m3Range(scale({ low: fallen * coeff.low, high: fallen * coeff.high }, flowT))}</dd>
        </div>
        <div className={mode === 'plan' ? 'kept' : 'lost'}>
          <dt>{mode === 'plan' ? 'Zatrzymasz z planem' : 'Zatrzymane celowo'}</dt>
          <dd>{mode === 'plan' ? fmt.m3Range(scale(kept, flowT)) : fmt.m3(0)}</dd>
        </div>
      </dl>

      <p className="rain-caption">
        {mode === 'plan'
          ? `Oczka i obniżenia (${fmt.m3Range(sites)})${weirs > 0 ? ` oraz zastawki na rowach (${fmt.m3(weirs)})` : ''} trzymają wodę na działce: wsiąka, zamiast odpłynąć.`
          : 'Bez zmian woda stoi w zastoiskach, gdzie uprawa wymaka, albo odpływa rowami poza działkę.'}
      </p>

      <p className="visually-hidden" role="status">
        {phase === 'done' &&
          (mode === 'plan'
            ? `Po ulewie ${rain} mm z planem na działce zostaje ${fmt.m3Range(kept)} wody.`
            : `Po ulewie ${rain} mm bez zmian woda spływa po powierzchni: ${fmt.m3Range({ low: fallen * coeff.low, high: fallen * coeff.high })}.`)}
      </p>

      <div className="rain-actions">
        {phase === 'raining' ? (
          <button type="button" onClick={stop}>
            Zatrzymaj
          </button>
        ) : (
          <button type="button" className="primary" onClick={play}>
            {phase === 'done' ? 'Puść jeszcze raz' : `Puść ulewę ${rain} mm`}
          </button>
        )}
        {phase === 'done' && (
          <button type="button" className="quiet" onClick={stop}>
            Wyczyść
          </button>
        )}
      </div>
      <p className="muted fine">
        Animacja pokazuje drogi spływu z modelu terenu LIDAR. Objętości z analizy: spływ{' '}
        {fmt.share(coeff.low)}–{fmt.share(coeff.high)} deszczu, zależnie od stanu gleby.
      </p>
    </section>
  )
}
