import { useEffect, useState } from 'react'

const reduced = () => window.matchMedia('(prefers-reduced-motion: reduce)').matches

/** Animates a number from 0 to `target` (ease-out), so key results arrive with emphasis. */
export function useCountUp(target: number, durationMs = 900): number {
  const [value, setValue] = useState(0)
  const still = reduced()
  useEffect(() => {
    if (still) return
    let frame = 0
    const start = performance.now()
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs)
      setValue(target * (1 - (1 - t) ** 3))
      if (t < 1) frame = requestAnimationFrame(step)
    }
    frame = requestAnimationFrame(step)
    return () => cancelAnimationFrame(frame)
  }, [target, durationMs, still])
  return still ? target : value
}
