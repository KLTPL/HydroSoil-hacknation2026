export const TABS = {
  parcels: 'Moje działki',
  batch: 'Analiza zbiorcza',
  archive: 'Archiwum raportów',
} as const

export type AccountTab = keyof typeof TABS
export const TAB_KEYS = Object.keys(TABS) as AccountTab[]

/** The open tab lives in the URL hash (`t=`) next to the share-link parameters. */
export function readTab(): AccountTab | null {
  const value = new URLSearchParams(window.location.hash.slice(1)).get('t')
  return TAB_KEYS.includes(value as AccountTab) ? (value as AccountTab) : null
}

export function writeTab(tab: AccountTab | null) {
  const params = new URLSearchParams(window.location.hash.slice(1))
  if (tab) params.set('t', tab)
  else params.delete('t')
  const hash = params.toString()
  window.history.replaceState(null, '', hash ? `#${hash}` : window.location.pathname + window.location.search)
}
