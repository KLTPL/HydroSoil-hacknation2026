import type { AnalysisReport, Crop, ModuleProgress, Parcel } from './model'

export type * from './model'

export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal })
  if (!response.ok) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, body?.detail ?? `Błąd serwera (${response.status})`)
  }
  return response.json() as Promise<T>
}

const query = (params: Record<string, string>) => new URLSearchParams(params).toString()

export const fetchCrops = () => getJson<Crop[]>('/api/crops')

export const searchParcels = (q: string, signal?: AbortSignal) =>
  getJson<Parcel[]>(`/api/parcels/search?${query({ q })}`, signal)

export const fetchParcelAt = (lon: number, lat: number, signal?: AbortSignal) =>
  getJson<Parcel>(`/api/parcels/at?${query({ lon: String(lon), lat: String(lat) })}`, signal)

/** `poll` only collects results of slow modules that finished in the background. */
export const fetchAnalysis = (
  parcelId: string,
  crop: string,
  date: string,
  signal?: AbortSignal,
  poll = false,
) =>
  getJson<AnalysisReport>(
    `/api/analysis?${query({ parcel_id: parcelId, crop, date, poll: String(poll) })}`,
    signal,
  )

export const reliefUrl = (parcelId: string, version: string) =>
  `/api/terrain/relief.png?${query({ parcel_id: parcelId, v: version })}`

/**
 * Streamed analysis: `onModule` hears each data source as it finishes, then the report
 * resolves. Server-sent events over fetch (EventSource cannot be aborted per request).
 */
export async function streamAnalysis(
  parcelId: string,
  crop: string,
  date: string,
  onModule: (progress: ModuleProgress) => void,
  signal: AbortSignal,
): Promise<AnalysisReport> {
  const url = `/api/analysis/stream?${query({ parcel_id: parcelId, crop, date })}`
  const response = await fetch(url, { signal, headers: { Accept: 'text/event-stream' } })
  if (!response.ok || !response.body) {
    const body = await response.json().catch(() => null)
    throw new ApiError(response.status, body?.detail ?? `Błąd serwera (${response.status})`)
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
      if (event?.type === 'module') onModule(JSON.parse(event.data) as ModuleProgress)
      if (event?.type === 'report') return JSON.parse(event.data) as AnalysisReport
    }
  }
  throw new ApiError(502, 'Połączenie z serwerem przerwało się w trakcie analizy. Spróbuj ponownie.')
}

function parseEvent(block: string): { type: string; data: string } | null {
  let type = 'message'
  const data: string[] = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) type = line.slice(6).trim()
    else if (line.startsWith('data:')) data.push(line.slice(5).trimStart())
  }
  return data.length ? { type, data: data.join('\n') } : null // comments/pings carry no data
}
