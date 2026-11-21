import { useEffect, useState } from 'react'
import type { Parcel } from '../model'
import { errorMessage } from '../useParcelReport'
import { fetchArchived, type ArchivedReport, type SavedParcel } from './accountApi'
import { AccountButton, SaveParcelButton } from './AccountControls'
import { AccountView } from './AccountView'
import { ArchivedView } from './ArchivedView'
import { readTab, writeTab } from './tabHash'
import { useAccount } from './useAccount'

type View = { kind: 'analysis' } | { kind: 'account' } | { kind: 'archived'; archived: ArchivedReport }

interface Options {
  parcel: Parcel | null
  crop: string
  date: string
  selectedSiteId: number | null
  onDateChange: (date: string) => void
  onSelectSite: (id: number | null) => void
  /** Opens a saved parcel's live analysis in the main flow. */
  onOpenSaved: (saved: SavedParcel) => void
}

/** Everything the optional account adds to the panel, as slots the panel renders.
 * Logged out, it is just the small "Zaloguj się" button. */
export function useAccountPanel(options: Options) {
  const account = useAccount()
  // A link with `t=<tab>` opens the account on that tab.
  const [view, setView] = useState<View>(() => (readTab() ? { kind: 'account' } : { kind: 'analysis' }))
  const [error, setError] = useState<string | null>(null)
  useEffect(() => {
    if (view.kind !== 'account') writeTab(null)
  }, [view.kind])

  const openAccount = () => {
    setError(null)
    setView({ kind: 'account' })
    if (account.state.status === 'user') void account.refreshSaved()
  }

  const openReport = async (reportId: number) => {
    setError(null)
    try {
      const archived = await fetchArchived(reportId)
      options.onSelectSite(null)
      setView({ kind: 'archived', archived })
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  let replacement = null
  if (view.kind === 'account') {
    replacement = (
      <>
        {error && <p className="error">{error}</p>}
        <AccountView
          account={account}
          date={options.date}
          onDateChange={options.onDateChange}
          onOpenSaved={(saved) => {
            setView({ kind: 'analysis' })
            options.onOpenSaved(saved)
          }}
          onOpenReport={(id) => void openReport(id)}
          onClose={() => setView({ kind: 'analysis' })}
        />
      </>
    )
  } else if (view.kind === 'archived') {
    replacement = (
      <ArchivedView
        archived={view.archived}
        selectedSiteId={options.selectedSiteId}
        onSelectSite={options.onSelectSite}
        onBack={openAccount}
      />
    )
  }

  return {
    /** Archived report on screen (the map shows its parcel and terrain), if any. */
    archived: view.kind === 'archived' ? view.archived.report : null,
    close: () => setView({ kind: 'analysis' }),
    slots: {
      headerAction: <AccountButton account={account} onOpen={openAccount} />,
      parcelAction: options.parcel && (
        <SaveParcelButton account={account} parcel={options.parcel} crop={options.crop} />
      ),
      replacement,
    },
  }
}
