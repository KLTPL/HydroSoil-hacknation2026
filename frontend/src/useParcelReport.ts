import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  fetchAnalysis,
  fetchParcelAt,
  searchParcels,
  type AnalysisReport,
  type ModuleResult,
  type Parcel,
} from './api'

export type Lookup = { status: 'idle' | 'loading' } | { status: 'error'; message: string }

export type ReportState =
  | { status: 'idle' | 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; report: AnalysisReport }

const POLL_MS = 4000
const MAX_POLL_FAILURES = 5

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message
  return 'Nie udało się połączyć z serwerem. Spróbuj ponownie.'
}

export const todayIso = () => new Date().toLocaleDateString('sv-SE') // YYYY-MM-DD, local time

/** Share/demo links: #p=<parcel id>&c=<crop id>&d=<YYYY-MM-DD> */
export function readHash(): { parcelId?: string; crop?: string; date?: string } {
  const params = new URLSearchParams(window.location.hash.slice(1))
  return {
    parcelId: params.get('p') ?? undefined,
    crop: params.get('c') ?? undefined,
    date: params.get('d') ?? undefined,
  }
}

function writeHash(parcelId: string, crop: string, date: string) {
  const params = new URLSearchParams({ p: parcelId, c: crop, d: date })
  window.history.replaceState(null, '', `#${params}`)
}

export function useParcelReport() {
  const [parcel, setParcel] = useState<Parcel | null>(null)
  const [lookup, setLookup] = useState<Lookup>({ status: 'idle' })
  const [report, setReport] = useState<ReportState>({ status: 'idle' })
  const inFlight = useRef<AbortController | null>(null)

  const restart = () => {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    return controller
  }

  const choose = useCallback((next: Parcel) => {
    restart()
    setParcel(next)
    setLookup({ status: 'idle' })
    setReport({ status: 'idle' })
  }, [])

  const pickAt = useCallback(async (lon: number, lat: number) => {
    const controller = restart()
    setLookup({ status: 'loading' })
    try {
      const found = await fetchParcelAt(lon, lat, controller.signal)
      setParcel(found)
      setReport({ status: 'idle' })
      setLookup({ status: 'idle' })
    } catch (error) {
      if (!controller.signal.aborted) setLookup({ status: 'error', message: errorMessage(error) })
    }
  }, [])

  const loadById = useCallback(async (parcelId: string): Promise<Parcel | null> => {
    const controller = restart()
    setLookup({ status: 'loading' })
    try {
      const [found] = await searchParcels(parcelId, controller.signal)
      if (!found) {
        setLookup({ status: 'error', message: 'Nie znaleziono działki o tym numerze.' })
        return null
      }
      setParcel(found)
      setReport({ status: 'idle' })
      setLookup({ status: 'idle' })
      return found
    } catch (error) {
      if (!controller.signal.aborted) setLookup({ status: 'error', message: errorMessage(error) })
      return null
    }
  }, [])

  const analyze = useCallback(async (target: Parcel, crop: string, date: string) => {
    const controller = restart()
    setReport({ status: 'loading' })
    writeHash(target.id, crop, date)
    try {
      const result = await fetchAnalysis(target.id, crop, date, controller.signal)
      setReport({ status: 'done', report: result })
    } catch (error) {
      if (!controller.signal.aborted) setReport({ status: 'error', message: errorMessage(error) })
    }
  }, [])

  // Terrain and satellite may still be downloading when the report arrives; poll until
  // they settle. The polled report also refreshes the diagnosis with the new data.
  const pending =
    report.status === 'done' &&
    (report.report.terrain.status === 'pending' || report.report.satellite.status === 'pending')
      ? report.report
      : null
  // Transient failures (server restarting, flaky network) are retried before giving up.
  const [pollFailures, setPollFailures] = useState(0)
  useEffect(() => {
    if (!pending) return
    const controller = new AbortController()
    const { parcel: target, crop, analysis_date } = pending
    const timer = window.setTimeout(async () => {
      try {
        const next = await fetchAnalysis(target.id, crop.id, analysis_date, controller.signal, true)
        setPollFailures(0)
        setReport((current) =>
          current.status === 'done' && current.report === pending
            ? { status: 'done', report: next }
            : current,
        )
      } catch (error) {
        if (controller.signal.aborted) return
        if (isTransient(error) && pollFailures < MAX_POLL_FAILURES) {
          setPollFailures((n) => n + 1) // re-runs this effect: next attempt
          return
        }
        setPollFailures(0)
        const message = errorMessage(error)
        setReport((current) =>
          current.status === 'done' && current.report === pending
            ? {
                status: 'done',
                report: {
                  ...current.report,
                  terrain: settle(current.report.terrain, message),
                  satellite: settle(current.report.satellite, message),
                },
              }
            : current,
        )
      }
    }, POLL_MS)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [pending, pollFailures])

  return { parcel, lookup, report, choose, pickAt, loadById, analyze }
}

function settle<T>(module: ModuleResult<T>, message: string): ModuleResult<T> {
  return module.status === 'pending' ? { ...module, status: 'unavailable', message } : module
}

function isTransient(error: unknown): boolean {
  if (error instanceof ApiError) return [502, 503, 504].includes(error.status)
  return true // network error
}
