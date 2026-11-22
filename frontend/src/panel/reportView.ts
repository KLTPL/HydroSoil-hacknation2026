import { createContext, useContext, useMemo, useState } from 'react'
import type { AnalysisReport } from '../model'

export type TabId = 'assessment' | 'plan' | 'data'

/** The open report tab and plan step. Lives above the panel so the map can show and open steps. */
export interface ReportView {
  tab: TabId
  /** Key of the open plan step, if any. */
  step: string | null
  setTab: (tab: TabId) => void
  setStep: (key: string | null) => void
  /** Switches to the plan and opens one step (a click on the map). */
  showStep: (key: string) => void
}

export const ReportViewContext = createContext<ReportView | null>(null)

export function useReportView(): ReportView {
  const view = useContext(ReportViewContext)
  if (!view) throw new Error('useReportView must be used inside ReportViewContext')
  return view
}

interface State {
  key: string
  tab: TabId
  step: string | null
}

// Polling replaces the report object when terrain arrives; the view only resets for another
// parcel, crop or date.
const reportKey = (report: AnalysisReport | null) =>
  report ? `${report.parcel.id}|${report.crop.id}|${report.analysis_date}` : ''

const fresh = (key: string): State => ({ key, tab: 'assessment', step: null })

export function useReportViewState(report: AnalysisReport | null): ReportView {
  const key = reportKey(report)
  const [state, setState] = useState<State>(() => fresh(key))
  const current = state.key === key ? state : fresh(key)
  const { tab, step } = current
  return useMemo(() => {
    const update = (change: Partial<State>) =>
      setState((s) => ({ ...(s.key === key ? s : fresh(key)), ...change }))
    return {
      tab,
      step,
      setTab: (next) => update({ tab: next }),
      setStep: (next) => update({ step: next }),
      showStep: (next) => update({ tab: 'plan', step: next }),
    }
  }, [key, tab, step])
}
