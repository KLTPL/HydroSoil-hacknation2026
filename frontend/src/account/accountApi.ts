// Optional account API (mirrors backend/src/retencja_api/accounts/schemas.py).
import { ApiError, parseEvent } from '../api'
import type { AnalysisReport, DroughtLevel } from '../model'

export interface Me {
  username: string | null
}

export interface SavedParcel {
  id: number
  parcel_id: string
  crop: string
  name: string | null
  number: string
  region: string
  commune: string
  area_ha: number
  created_at: string
  last_analysed_at: string | null
}

export interface ReportSummary {
  id: number
  parcel_id: string
  crop: string
  analysis_date: string
  generated_at: string
  level: DroughtLevel
  water_pct: number | null
  top_recommendation: string | null
}

export interface ArchivedReport {
  summary: ReportSummary
  previous: ReportSummary | null
  report: AnalysisReport
}

export interface BatchRow {
  saved_id: number
  parcel_id: string
  name: string | null
  number: string
  region: string
  crop: string
  status: 'ok' | 'error'
  message: string | null
  level: DroughtLevel | null
  headline: string | null
  water_pct: number | null
  top_recommendation: string | null
  analysed_at: string | null
  report_id: number | null
}

const BASE = '/api/account'

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  // The custom header marks the request as coming from this app (CSRF protection).
  const headers: Record<string, string> = method === 'GET' ? {} : { 'X-Splyw': '1' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const response = await fetch(`${BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!response.ok) {
    const detail = await response.json().catch(() => null)
    throw new ApiError(response.status, errorText(detail?.detail, response.status))
  }
  return (response.status === 204 ? undefined : await response.json()) as T
}

/** FastAPI validation errors arrive as a list; show something a farmer understands. */
function errorText(detail: unknown, status: number): string {
  if (typeof detail === 'string') return detail
  if (status === 422) {
    return 'Nazwa: 3–32 znaki (litery bez polskich znaków, cyfry, . _ -). Hasło: 8–128 znaków.'
  }
  return `Błąd serwera (${status})`
}

export const fetchMe = () => request<Me>('GET', '/me')
export const register = (username: string, password: string) =>
  request<Me>('POST', '/register', { username, password })
export const login = (username: string, password: string) =>
  request<Me>('POST', '/login', { username, password })
export const logout = () => request<Me>('POST', '/logout')

export const fetchSaved = () => request<SavedParcel[]>('GET', '/parcels')
export const saveParcel = (parcelId: string, crop: string, name?: string) =>
  request<SavedParcel>('POST', '/parcels', { parcel_id: parcelId, crop, name })
export const updateSaved = (id: number, changes: { name?: string; crop?: string }) =>
  request<SavedParcel>('PATCH', `/parcels/${id}`, changes)
export const removeSaved = (id: number) => request<void>('DELETE', `/parcels/${id}`)

export const fetchReports = (parcelId?: string) =>
  request<ReportSummary[]>(
    'GET',
    `/reports${parcelId ? `?${new URLSearchParams({ parcel_id: parcelId })}` : ''}`,
  )
export const fetchArchived = (id: number) => request<ArchivedReport>('GET', `/reports/${id}`)

/** Batch analysis: `onRow` hears each saved parcel as soon as its report is ready. */
export async function streamBatch(
  date: string,
  onRow: (row: BatchRow) => void,
  signal: AbortSignal,
): Promise<void> {
  const url = `${BASE}/batch/stream?${new URLSearchParams({ date })}`
  const response = await fetch(url, { signal, headers: { Accept: 'text/event-stream' } })
  if (!response.ok || !response.body) {
    const detail = await response.json().catch(() => null)
    throw new ApiError(response.status, errorText(detail?.detail, response.status))
  }
  const reader = response.body.pipeThrough(new TextDecoderStream()).getReader()
  let buffer = ''
  for (;;) {
    const { value, done } = await reader.read()
    if (done) break
    buffer += value
    let boundary: number
    while ((boundary = buffer.indexOf('\n\n')) >= 0) {
      const event = parseEvent(buffer.slice(0, boundary))
      buffer = buffer.slice(boundary + 2)
      if (event?.type === 'row') onRow(JSON.parse(event.data) as BatchRow)
      if (event?.type === 'done') return
    }
  }
  throw new ApiError(502, 'Połączenie przerwało się w trakcie analizy zbiorczej. Spróbuj ponownie.')
}
