import type { ReactNode } from 'react'
import type { ModuleResult } from '../api'
import { Busy } from './Busy'
import { DataRow } from './DataRow'
import { Sources } from './Sources'

/** Data row for one module: pending, unavailable (with the reason) or its content. */
export function ModuleSection<T>({
  id,
  title,
  module,
  summary,
  children,
}: {
  id: string
  title: string
  module: ModuleResult<T>
  summary: (data: T) => ReactNode
  children: (data: T) => ReactNode
}) {
  const data = module.status === 'ok' ? module.data : null
  const shortStatus = module.status === 'pending' ? 'pobieram…' : 'brak danych'
  return (
    <DataRow id={id} title={title} summary={data !== null ? summary(data) : shortStatus}>
      {module.status === 'pending' && <Busy label={module.message ?? 'Pobieram dane…'} />}
      {module.status === 'unavailable' && <p className="notice">Brak danych: {module.message}</p>}
      {data !== null && (
        <>
          {module.message && <p className="notice">{module.message}</p>}
          {children(data)}
        </>
      )}
      <Sources sources={module.sources} />
    </DataRow>
  )
}
