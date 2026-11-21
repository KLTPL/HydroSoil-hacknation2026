import { useEffect, useState, type KeyboardEvent } from 'react'
import { fetchCrops, type Crop } from '../api'
import { earliestIso } from '../dates'
import { todayIso } from '../useParcelReport'
import type { SavedParcel } from './accountApi'
import { BatchTable } from './BatchTable'
import { LoginForm } from './LoginForm'
import { MyParcels } from './MyParcels'
import { readTab, TAB_KEYS, TABS, writeTab, type AccountTab } from './tabHash'
import { ReportArchive } from './ReportArchive'
import type { Account } from './useAccount'

type Tab = AccountTab

interface Props {
  account: Account
  date: string
  onDateChange: (date: string) => void
  onOpenSaved: (saved: SavedParcel) => void
  onOpenReport: (reportId: number) => void
  onClose: () => void
}

export function BackButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" className="quiet back no-print" onClick={onClick}>
      <span aria-hidden="true">←</span> {label}
    </button>
  )
}

export function AccountView({ account, date, onDateChange, onOpenSaved, onOpenReport, onClose }: Props) {
  const [tab, setTabState] = useState<Tab>(() => readTab() ?? 'parcels')
  const setTab = (next: Tab) => {
    setTabState(next)
    writeTab(next)
  }

  // Tabs pattern: arrows, Home and End move between tabs; Tab goes into the panel.
  function onTabKey(event: KeyboardEvent<HTMLDivElement>) {
    const moves: Record<string, number> = { ArrowRight: 1, ArrowLeft: -1, Home: -TAB_KEYS.length, End: TAB_KEYS.length }
    if (!(event.key in moves)) return
    event.preventDefault()
    const i = TAB_KEYS.indexOf(tab) + moves[event.key]
    const next = TAB_KEYS[Math.min(TAB_KEYS.length - 1, Math.max(0, i))]
    setTab(next)
    document.getElementById(`tab-${next}`)?.focus()
  }
  const [crops, setCrops] = useState<Crop[]>([])
  const today = todayIso()

  useEffect(() => {
    void fetchCrops().then(setCrops)
  }, [])

  const cropName = (id: string) => crops.find((c) => c.id === id)?.name ?? id
  const { state } = account

  return (
    <section className="account" aria-label="Konto">
      <div className="account-bar">
        <BackButton onClick={onClose} label="Wróć do analizy" />
        {state.status === 'user' && (
          <button type="button" className="quiet small" onClick={() => void account.signOut()}>
            Wyloguj ({state.username})
          </button>
        )}
      </div>
      {state.status === 'checking' && <p className="muted">Sprawdzam konto…</p>}
      {state.status === 'anonymous' && <LoginForm account={account} />}
      {state.status === 'user' && (
        <>
          <div className="tabs" role="tablist" aria-label="Twoje dane" onKeyDown={onTabKey}>
            {TAB_KEYS.map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                id={`tab-${key}`}
                aria-selected={tab === key}
                tabIndex={tab === key ? 0 : -1}
                aria-controls="account-tabpanel"
                className={tab === key ? 'tab active' : 'tab'}
                onClick={() => setTab(key)}
              >
                {TABS[key]}
              </button>
            ))}
          </div>
          <div id="account-tabpanel" role="tabpanel" tabIndex={0} aria-labelledby={`tab-${tab}`} className="tab-body">
            {tab === 'parcels' && (
              <MyParcels account={account} cropName={cropName} onOpen={onOpenSaved} />
            )}
            {tab === 'batch' && (
              <BatchTable
                account={account}
                date={date}
                minDate={earliestIso(today)}
                maxDate={today}
                onDateChange={onDateChange}
                onOpenReport={onOpenReport}
              />
            )}
            {tab === 'archive' && (
              <ReportArchive saved={account.saved} cropName={cropName} onOpenReport={onOpenReport} />
            )}
          </div>
        </>
      )}
    </section>
  )
}
