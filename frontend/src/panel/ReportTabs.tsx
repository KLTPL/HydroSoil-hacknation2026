import { useEffect, useId, useRef, type KeyboardEvent, type ReactNode } from 'react'

export interface Tab<T extends string> {
  id: T
  label: ReactNode
  content: ReactNode
}

/** Nearest ancestor that scrolls vertically (the panel, or the phone sheet). */
function scrollParent(element: HTMLElement): HTMLElement | null {
  for (let node = element.parentElement; node; node = node.parentElement) {
    if (/(auto|scroll)/.test(getComputedStyle(node).overflowY)) return node
  }
  return null
}

/**
 * Report parts as tabs under a bar that sticks to the top of the panel. Every tab stays in
 * the DOM (inactive ones hidden) so the printed report still contains all of them.
 */
interface Props<T extends string> {
  tabs: Tab<T>[]
  active: T
  onSelect: (id: T) => void
  actions?: ReactNode
}

export function ReportTabs<T extends string>({ tabs, active, onSelect, actions }: Props<T>) {
  const base = useId()
  const root = useRef<HTMLDivElement>(null)
  const buttons = useRef(new Map<string, HTMLButtonElement>())
  const tabId = (id: string) => `${base}-tab-${id}`
  const panelId = (id: string) => `${base}-panel-${id}`

  // Switching from deep inside a long tab starts the new one at its top, not mid-way.
  useEffect(() => {
    const element = root.current
    const scroller = element && scrollParent(element)
    if (!element || !scroller) return
    const above = scroller.getBoundingClientRect().top + scroller.clientTop - element.getBoundingClientRect().top
    if (above > 0) scroller.scrollTop -= above
  }, [active])

  // Arrow keys move between tabs and open them (automatic activation).
  function onKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    const index = tabs.findIndex((t) => t.id === active)
    const next = {
      ArrowRight: (index + 1) % tabs.length,
      ArrowLeft: (index - 1 + tabs.length) % tabs.length,
      Home: 0,
      End: tabs.length - 1,
    }[event.key]
    if (next === undefined) return
    event.preventDefault()
    onSelect(tabs[next].id)
    buttons.current.get(tabs[next].id)?.focus()
  }

  return (
    <div ref={root} className="tabbed">
      <div className="tab-bar no-print">
        <div role="tablist" aria-label="Części raportu" className="tab-list" onKeyDown={onKeyDown}>
          {tabs.map((tab) => (
            <button
              key={tab.id}
              ref={(button) => {
                if (button) buttons.current.set(tab.id, button)
                else buttons.current.delete(tab.id)
              }}
              id={tabId(tab.id)}
              type="button"
              role="tab"
              className="report-tab"
              aria-selected={tab.id === active}
              aria-controls={panelId(tab.id)}
              tabIndex={tab.id === active ? 0 : -1}
              onClick={() => onSelect(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>
        {actions}
      </div>
      {tabs.map((tab) => (
        <div
          key={tab.id}
          id={panelId(tab.id)}
          role="tabpanel"
          className={`tab-panel tab-panel-${tab.id}`}
          aria-labelledby={tabId(tab.id)}
          tabIndex={0}
          hidden={tab.id !== active}
        >
          {tab.content}
        </div>
      ))}
    </div>
  )
}
