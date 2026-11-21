import { useEffect, useId, useRef, useState } from 'react'
import * as fmt from '../format'
import { LEVEL } from '../panel/levels'
import { errorMessage } from '../useParcelReport'
import { streamBatch, type BatchRow, type SavedParcel } from './accountApi'
import { parcelLabel } from './labels'
import type { Account } from './useAccount'

interface Props {
  account: Account
  date: string
  minDate: string
  maxDate: string
  onDateChange: (date: string) => void
  onOpenReport: (reportId: number) => void
}

// Most urgent first: severe drought on top, parcels still being analysed last.
const URGENCY = { severe: 0, moderate: 1, watch: 2, none: 3 } as const

function urgency(row: BatchRow | undefined): number {
  if (!row) return 6
  if (row.status === 'error' || !row.level) return 5
  return URGENCY[row.level]
}

function Cells({ saved, row }: { saved: SavedParcel; row: BatchRow | undefined }) {
  if (!row) {
    return (
      <td colSpan={3} className="muted">
        <span className="batch-wait" aria-hidden="true" /> liczę…
      </td>
    )
  }
  if (row.status === 'error' || !row.level) {
    return (
      <td colSpan={3} className="error fine">
        {row.message ?? `Nie udało się przeanalizować działki ${saved.number}`}
      </td>
    )
  }
  const level = LEVEL[row.level]
  return (
    <>
      <td>
        <span className={`batch-level tone-${level.tone}`}>{level.label}</span>
      </td>
      <td className="num">{row.water_pct === null ? '–' : fmt.pct(row.water_pct)}</td>
      <td className="batch-action">{row.top_recommendation ?? '–'}</td>
    </>
  )
}

export function BatchTable({ account, date, minDate, maxDate, onDateChange, onOpenReport }: Props) {
  const dateId = useId()
  const [rows, setRows] = useState<Map<number, BatchRow>>(new Map())
  const [status, setStatus] = useState<'idle' | 'running' | 'done'>('idle')
  const [error, setError] = useState<string | null>(null)
  const inFlight = useRef<AbortController | null>(null)

  useEffect(() => () => inFlight.current?.abort(), [])

  async function run() {
    inFlight.current?.abort()
    const controller = new AbortController()
    inFlight.current = controller
    setRows(new Map())
    setError(null)
    setStatus('running')
    try {
      await streamBatch(
        date,
        (row) => setRows((current) => new Map(current).set(row.saved_id, row)),
        controller.signal,
      )
      setStatus('done')
      void account.refreshSaved() // "last analysed" changed
    } catch (err) {
      if (controller.signal.aborted) return
      setError(errorMessage(err))
      setStatus('done')
    }
  }

  if (account.saved.length === 0) {
    return <p className="notice">Najpierw zapisz działki w zakładce „Moje działki”.</p>
  }

  const ordered = [...account.saved].sort((a, b) => urgency(rows.get(a.id)) - urgency(rows.get(b.id)))
  const done = account.saved.filter((s) => rows.has(s.id)).length

  return (
    <>
      <form
        className="batch-form"
        onSubmit={(e) => {
          e.preventDefault()
          void run()
        }}
      >
        <div className="field">
          <label htmlFor={dateId}>Stan na dzień</label>
          <input
            id={dateId}
            type="date"
            value={date}
            min={minDate}
            max={maxDate}
            required
            onChange={(e) => onDateChange(e.target.value)}
          />
        </div>
        <button type="submit" className="primary" disabled={status === 'running'}>
          {status === 'running'
            ? `Analizuję ${done}/${account.saved.length}…`
            : `Sprawdź ${account.saved.length} ${fmt.plural(account.saved.length, 'działkę', 'działki', 'działek')}`}
        </button>
      </form>
      {status === 'idle' && (
        <p className="muted fine">
          Każda działka to pełna analiza z 7 źródeł; pierwsze sprawdzenie nowego miejsca może
          potrwać kilka minut. Wyniki pojawiają się na bieżąco, najpilniejsze na górze.
        </p>
      )}
      <div aria-live="polite">{error && <p className="error">{error}</p>}</div>
      {status !== 'idle' && (
        <div className="batch-scroll">
          <table className="batch-table">
            <thead>
              <tr>
                <th scope="col">Działka</th>
                <th scope="col">Ocena</th>
                <th scope="col" className="num">Woda</th>
                <th scope="col">Najważniejsze działanie</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((saved) => {
                const row = rows.get(saved.id)
                return (
                  <tr key={saved.id}>
                    <th scope="row">
                      {row?.report_id ? (
                        <button
                          type="button"
                          className="link"
                          onClick={() => onOpenReport(row.report_id!)}
                        >
                          {parcelLabel(saved)}
                        </button>
                      ) : (
                        parcelLabel(saved)
                      )}
                      {row?.analysed_at && (
                        <span className="muted fine block">{fmt.dateTime(row.analysed_at)}</span>
                      )}
                    </th>
                    <Cells saved={saved} row={row} />
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
