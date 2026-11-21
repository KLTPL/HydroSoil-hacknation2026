/** "Print / save as PDF": the map first renders a snapshot of the parcel, then prints. */
export const PRINT_EVENT = 'report:print'

export function requestPrint() {
  window.dispatchEvent(new Event(PRINT_EVENT))
}
