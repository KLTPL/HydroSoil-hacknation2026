import type { ReactNode } from 'react'
import type { ModuleResult } from '../api'
import { Busy } from './Busy'
import { Sources } from './Sources'

/** Report section for one data module: pending, unavailable (with the reason) or content. */
export function ModuleSection<T>({
  id,
  title,
  module,
  children,
}: {
  id: string
  title: string
  module: ModuleResult<T>
  children: (data: T) => ReactNode
}) {
  return (
    <section className="report-section" aria-labelledby={`${id}-heading`}>
      <h3 id={`${id}-heading`}>{title}</h3>
      {module.status === 'pending' && <Busy label={module.message ?? 'Pobieram dane…'} />}
      {module.status === 'unavailable' && (
        <p className="notice">Brak danych: {module.message}</p>
      )}
      {module.status === 'ok' && module.data !== null && (
        <>
          {module.message && <p className="notice">{module.message}</p>}
          {children(module.data)}
        </>
      )}
      <Sources sources={module.sources} />
    </section>
  )
}
