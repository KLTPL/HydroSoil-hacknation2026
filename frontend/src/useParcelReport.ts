import { useCallback, useEffect, useRef, useState } from 'react'
import {
  ApiError,
  fetchAnalysis,
  fetchParcelAt,
  fetchTerrain,
  searchParcels,
  type AnalysisReport,
  type Parcel,
} from './api'

export type Lookup = { status: 'idle' | 'loading' } | { status: 'error'; message: string }

export type ReportState =
  | { status: 'idle' | 'loading' }
  | { status: 'error'; message: string }
  | { status: 'done'; report: AnalysisReport }

const TERRAIN_POLL_MS = 4000

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

  // Terrain may still be downloading when the report arrives; poll until it settles.
  const pendingParcelId =
    report.status === 'done' && report.report.terrain.status === 'pending'
      ? report.report.parcel.id
      : null
  useEffect(() => {
    if (!pendingParcelId) return
    const controller = new AbortController()
    const timer = window.setTimeout(async () => {
      try {
        const terrain = await fetchTerrain(pendingParcelId, controller.signal)
        setReport((current) =>
          current.status === 'done' && current.report.parcel.id === pendingParcelId
            ? { status: 'done', report: { ...current.report, terrain } }
            : current,
        )
      } catch (error) {
        if (controller.signal.aborted) return
        const message = errorMessage(error)
        setReport((current) =>
          current.status === 'done'
            ? {
                status: 'done',
                report: {
                  ...current.report,
                  terrain: { ...current.report.terrain, status: 'unavailable', message },
                },
              }
            : current,
        )
      }
    }, TERRAIN_POLL_MS)
    return () => {
      controller.abort()
      window.clearTimeout(timer)
    }
  }, [pendingParcelId, report])

  return { parcel, lookup, report, choose, pickAt, loadById, analyze }
}
