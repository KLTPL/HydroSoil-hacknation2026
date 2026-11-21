import type { Map as MapLibreMap } from 'maplibre-gl'
import type { FlowPath } from '../model'

/** Rain falls for this long; the runoff then drains along the flow network. */
export const RAIN_MS = 3500
const MAX_MS = 11000
// Animation speed in screen pixels per second (real runoff moves ~0.1–1 m/s).
const DRAIN_SPEED_PX_S = 55
const TRAIL_FADE = 0.07 // share of the previous frame erased each frame (trail length)
const RAINDROPS = 260

interface Segment {
  coords: [number, number][]
  cum: number[] // distance from the start to each vertex (m)
  length: number
  speed: number // relative; scaled by metres per pixel each frame
  end: FlowPath['end']
  next: number | null
}

interface Particle {
  seg: number
  d: number
  vertex: number
  x?: number
  y?: number
}

interface Ripple {
  at: [number, number]
  born: number
  kept: boolean
}

export interface RainFrame {
  elapsed: number
  /** 0–1: share of the storm that has run through */
  progress: number
  done: boolean
}

const M_PER_DEG_LAT = 110_540

function toSegments(paths: FlowPath[]): Segment[] {
  return paths.map((p) => {
    const coords = p.geometry.coordinates as [number, number][]
    const mPerDegLon = 111_320 * Math.cos((coords[0][1] * Math.PI) / 180)
    const cum = [0]
    for (let i = 1; i < coords.length; i++) {
      const dx = (coords[i][0] - coords[i - 1][0]) * mPerDegLon
      const dy = (coords[i][1] - coords[i - 1][1]) * M_PER_DEG_LAT
      cum.push(cum[i - 1] + Math.hypot(dx, dy))
    }
    // Bigger streams run faster: the eye follows water to where it gathers.
    const speed = 1 + 0.3 * Math.log2(Math.max(p.area_m2, 800) / 800) // × px/s at this zoom
    return { coords, cum, length: cum[cum.length - 1], speed, end: p.end, next: p.next }
  })
}

/**
 * Rain-on-terrain animation drawn on a canvas over the map: drops fall, runoff particles
 * follow the LIDAR flow network and end either pooling in a hollow (blue ripple) or
 * leaving the area (amber ripple). Purely illustrative; volumes come from the analysis.
 */
export class FlowAnimation {
  private readonly canvas: HTMLCanvasElement
  private readonly ctx: CanvasRenderingContext2D
  private readonly segments: Segment[]
  private readonly spawnCdf: number[]
  private readonly totalParticles: number
  private particles: Particle[] = []
  private ripples: Ripple[] = []
  /** Water that reached a hollow stays visible there, so the hollows visibly fill up. */
  private pooled: [number, number][] = []
  private spawned = 0
  private started = 0
  private last = 0
  private raf = 0
  private readonly onMove = () => this.resetTrails()
  private readonly resize = () => this.fitCanvas()
  private readonly observer: ResizeObserver

  private readonly map: MapLibreMap
  private readonly onFrame: (frame: RainFrame) => void

  constructor(map: MapLibreMap, paths: FlowPath[], onFrame: (frame: RainFrame) => void) {
    this.map = map
    this.onFrame = onFrame
    this.segments = toSegments(paths).filter((s) => s.length > 0)
    let sum = 0
    this.spawnCdf = this.segments.map((s) => (sum += s.length))
    this.totalParticles = Math.min(2600, Math.max(500, this.segments.length * 5))

    this.canvas = document.createElement('canvas')
    this.canvas.className = 'flow-canvas'
    this.canvas.setAttribute('aria-hidden', 'true')
    map.getCanvasContainer().appendChild(this.canvas)
    this.ctx = this.canvas.getContext('2d')!
    this.observer = new ResizeObserver(this.resize)
    this.observer.observe(map.getContainer())
    this.fitCanvas()
    map.on('move', this.onMove)
  }

  play() {
    cancelAnimationFrame(this.raf)
    this.particles = []
    this.ripples = []
    this.pooled = []
    this.spawned = 0
    this.started = this.last = performance.now()
    this.clear()
    this.raf = requestAnimationFrame((t) => this.tick(t))
  }

  stop() {
    cancelAnimationFrame(this.raf)
    this.particles = []
    this.ripples = []
    this.pooled = []
    this.clear()
  }

  destroy() {
    cancelAnimationFrame(this.raf)
    this.map.off('move', this.onMove)
    this.observer.disconnect()
    this.canvas.remove()
  }

  private fitCanvas() {
    const { clientWidth, clientHeight } = this.map.getContainer()
    const dpr = window.devicePixelRatio || 1
    this.canvas.width = clientWidth * dpr
    this.canvas.height = clientHeight * dpr
    this.canvas.style.width = `${clientWidth}px`
    this.canvas.style.height = `${clientHeight}px`
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
  }

  private clear() {
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height)
  }

  /** Panning would smear trails across the screen; restart them from the new positions. */
  private resetTrails() {
    this.clear()
    for (const p of this.particles) p.x = p.y = undefined
    this.drawPooled()
  }

  private spawn(count: number) {
    const total = this.spawnCdf[this.spawnCdf.length - 1]
    for (let i = 0; i < count && this.spawned < this.totalParticles; i++, this.spawned++) {
      const r = Math.random() * total
      let lo = 0
      let hi = this.spawnCdf.length - 1
      while (lo < hi) {
        const mid = (lo + hi) >> 1
        if (this.spawnCdf[mid] < r) lo = mid + 1
        else hi = mid
      }
      const seg = this.segments[lo]
      const d = Math.random() * seg.length
      let vertex = 0
      while (seg.cum[vertex + 1] < d) vertex++
      this.particles.push({ seg: lo, d, vertex })
    }
  }

  /** Moves a particle; returns false once it has pooled or left the area. */
  private advance(p: Particle, dt: number, now: number, mpp: number): boolean {
    let seg = this.segments[p.seg]
    p.d += seg.speed * DRAIN_SPEED_PX_S * mpp * dt
    while (p.d >= seg.length) {
      if (seg.end === 'join' && seg.next !== null && this.segments[seg.next]) {
        p.d -= seg.length
        p.seg = seg.next
        p.vertex = 0
        seg = this.segments[p.seg]
        continue
      }
      const end = seg.coords[seg.coords.length - 1]
      if (seg.end === 'pool' && this.pooled.length < 4000) {
        // Scatter a little around the inflow point: a puddle, not a single dot.
        const jitter = () => (Math.random() - 0.5) * 0.00012
        this.pooled.push([end[0] + jitter(), end[1] + jitter() * 0.6])
      }
      if (this.ripples.length < 160 && Math.random() < 0.35) {
        this.ripples.push({ at: end, born: now, kept: seg.end === 'pool' })
      }
      return false
    }
    while (seg.cum[p.vertex + 1] < p.d) p.vertex++
    return true
  }

  private position(p: Particle): [number, number] {
    const seg = this.segments[p.seg]
    const i = p.vertex
    const a = seg.coords[i]
    const b = seg.coords[Math.min(i + 1, seg.coords.length - 1)]
    const span = seg.cum[i + 1] - seg.cum[i] || 1
    const t = (p.d - seg.cum[i]) / span
    return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
  }

  private tick(now: number) {
    const elapsed = now - this.started
    const dt = Math.min(0.05, (now - this.last) / 1000)
    this.last = now
    const ctx = this.ctx
    const { clientWidth: w, clientHeight: h } = this.map.getContainer()

    ctx.globalCompositeOperation = 'destination-out'
    ctx.fillStyle = `rgba(0,0,0,${TRAIL_FADE})`
    ctx.fillRect(0, 0, w, h)
    ctx.globalCompositeOperation = 'source-over'

    if (elapsed < RAIN_MS) {
      this.spawn(Math.ceil((this.totalParticles * dt * 1000) / RAIN_MS))
      this.drawRain(w, h, elapsed)
    }

    const centre = this.map.getCenter()
    // Web Mercator metres per CSS pixel at the map centre (512 px tiles).
    const mpp = (40_075_016 * Math.cos((centre.lat * Math.PI) / 180)) / (512 * 2 ** this.map.getZoom())
    ctx.beginPath()
    this.particles = this.particles.filter((p) => {
      const alive = this.advance(p, dt, now, mpp)
      if (!alive) return false
      const pt = this.map.project(this.position(p))
      if (p.x !== undefined && p.y !== undefined) {
        ctx.moveTo(p.x, p.y)
        ctx.lineTo(pt.x, pt.y)
      }
      p.x = pt.x
      p.y = pt.y
      return true
    })
    // Dark halo under a bright core: readable on the photo and on the pale relief alike.
    ctx.lineCap = 'round'
    ctx.strokeStyle = 'rgba(3, 32, 84, 0.6)'
    ctx.lineWidth = 5.5
    ctx.stroke()
    ctx.strokeStyle = 'rgba(130, 220, 255, 1)'
    ctx.lineWidth = 2.8
    ctx.stroke()
    this.drawPooled()
    this.drawRipples(now)

    const done = elapsed > RAIN_MS && (this.particles.length === 0 || elapsed > MAX_MS)
    this.onFrame({ elapsed, progress: Math.min(1, elapsed / MAX_MS), done })
    if (done) {
      this.particles = []
      this.fadeOut(0)
      return
    }
    this.raf = requestAnimationFrame((t) => this.tick(t))
  }

  private drawRain(w: number, h: number, elapsed: number) {
    const ctx = this.ctx
    const fade = Math.min(1, (RAIN_MS - elapsed) / 600)
    ctx.strokeStyle = `rgba(225, 240, 255, ${0.6 * fade})`
    ctx.lineWidth = 1.2
    ctx.beginPath()
    for (let i = 0; i < RAINDROPS * fade; i++) {
      const x = Math.random() * w
      const y = Math.random() * h
      ctx.moveTo(x, y)
      ctx.lineTo(x - 4, y + 18)
    }
    ctx.stroke()
  }

  private drawPooled() {
    const ctx = this.ctx
    ctx.fillStyle = 'rgba(30, 140, 255, 0.9)'
    ctx.beginPath()
    for (const at of this.pooled) {
      const pt = this.map.project(at)
      ctx.moveTo(pt.x + 3, pt.y)
      ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2)
    }
    ctx.fill()
  }

  private drawRipples(now: number) {
    const ctx = this.ctx
    this.ripples = this.ripples.filter((r) => {
      const age = (now - r.born) / 900
      if (age >= 1) return false
      const pt = this.map.project(r.at)
      ctx.beginPath()
      ctx.arc(pt.x, pt.y, 3 + age * 14, 0, Math.PI * 2)
      ctx.strokeStyle = r.kept
        ? `rgba(96, 196, 255, ${0.9 * (1 - age)})`
        : `rgba(255, 176, 64, ${0.9 * (1 - age)})`
      ctx.lineWidth = 2
      ctx.stroke()
      return true
    })
  }

  private fadeOut(frame: number) {
    const ctx = this.ctx
    const { clientWidth: w, clientHeight: h } = this.map.getContainer()
    ctx.globalCompositeOperation = 'destination-out'
    ctx.fillStyle = 'rgba(0,0,0,0.2)'
    ctx.fillRect(0, 0, w, h)
    ctx.globalCompositeOperation = 'source-over'
    if (frame < 30) this.raf = requestAnimationFrame(() => this.fadeOut(frame + 1))
    else {
      this.clear()
      this.drawPooled() // the water that stayed on the parcel remains visible
    }
  }
}
