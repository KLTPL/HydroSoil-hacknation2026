import { useEffect, useState } from 'react'
import { searchPlaces, type Place } from '../geocode'
import { errorMessage } from '../useParcelReport'

const MIN_LENGTH = 3
const DEBOUNCE_MS = 250

export type Suggestions =
  | { status: 'idle' }
  | { status: 'done'; query: string; places: Place[] }
  | { status: 'error'; message: string }

/** Places matching what the user is typing; only the latest query's answer is kept. */
export function usePlaceSuggestions(query: string, enabled: boolean): Suggestions {
  const [suggestions, setSuggestions] = useState<Suggestions>({ status: 'idle' })
  const q = query.trim()
  const active = enabled && q.length >= MIN_LENGTH

  useEffect(() => {
    if (!active) return
    const controller = new AbortController()
    const timer = window.setTimeout(() => {
      searchPlaces(q, controller.signal).then(
        (places) => setSuggestions({ status: 'done', query: q, places }),
        (error: unknown) => {
          // A newer keystroke cancelled this request; its answer no longer matters.
          if (controller.signal.aborted) return
          setSuggestions({ status: 'error', message: errorMessage(error) })
        },
      )
    }, DEBOUNCE_MS)
    return () => {
      window.clearTimeout(timer)
      controller.abort()
    }
  }, [q, active])

  return active ? suggestions : { status: 'idle' }
}
