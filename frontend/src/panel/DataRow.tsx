import { createContext, useContext, useId, type ReactNode } from 'react'

interface Group {
  open: string | null
  toggle: (id: string) => void
}

const GroupContext = createContext<Group | null>(null)

/** Rows inside open one at a time, so the list stays short enough to scan. The owner keeps
 * which row is open, so links elsewhere in the report can open one. */
export function RowGroup({
  open,
  onOpenChange,
  children,
}: {
  open: string | null
  onOpenChange: (id: string | null) => void
  children: ReactNode
}) {
  const toggle = (id: string) => onOpenChange(open === id ? null : id)
  return <GroupContext.Provider value={{ open, toggle }}>{children}</GroupContext.Provider>
}

interface Props {
  id: string
  title: string
  /** The one reading worth seeing without opening the row. */
  summary: ReactNode
  children: ReactNode
}

/** One data source: title and its key reading; opens to the full detail (always printed). */
export function DataRow({ id, title, summary, children }: Props) {
  const group = useContext(GroupContext)
  if (!group) throw new Error('DataRow must be rendered inside a RowGroup')
  const headingId = useId()
  const bodyId = useId()
  const open = group.open === id
  return (
    <section className="data-row" aria-labelledby={headingId}>
      <h3 id={headingId} className="data-row-heading">
        <button type="button" aria-expanded={open} aria-controls={bodyId} onClick={() => group.toggle(id)}>
          <span className="data-row-title">{title}</span>
          <span className="data-row-summary">{summary}</span>
        </button>
      </h3>
      <div id={bodyId} className="data-row-body" hidden={!open}>
        {children}
      </div>
    </section>
  )
}
