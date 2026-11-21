import type { Range } from './api'

const integer = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0 })
const decimal = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 1 })
const percent = new Intl.NumberFormat('pl-PL', { style: 'percent', maximumFractionDigits: 0 })

export const m3 = (value: number) => `${integer.format(value)} m³`
export const m2 = (value: number) => `${integer.format(value)} m²`
export const ha = (value: number) => `${decimal.format(value)} ha`
export const meters = (value: number) => `${decimal.format(value)} m`
export const share = (value: number) => percent.format(value)

export function m3Range({ low, high }: Range): string {
  if (Math.round(low) === Math.round(high)) return m3(high)
  return `${integer.format(low)}–${integer.format(high)} m³`
}
