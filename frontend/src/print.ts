/** "Print / save as PDF": the map first renders a snapshot of the parcel, then prints. */
export const PRINT_EVENT = 'report:print'

export function requestPrint() {
  window.dispatchEvent(new Event(PRINT_EVENT))
}

/**
 * The printed report must be complete: collapsed sections (<details>) are opened for
 * printing and closed again afterwards.
 */
export function expandDetailsWhenPrinting() {
  let reopened: HTMLDetailsElement[] = []
  window.addEventListener('beforeprint', () => {
    reopened = [...document.querySelectorAll<HTMLDetailsElement>('details:not([open])')]
    reopened.forEach((d) => (d.open = true))
  })
  window.addEventListener('afterprint', () => {
    reopened.forEach((d) => (d.open = false))
    reopened = []
  })
}
