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

const signed = new Intl.NumberFormat('pl-PL', { maximumFractionDigits: 0, signDisplay: 'exceptZero' })
const twoDecimals = new Intl.NumberFormat('pl-PL', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})

export const mm = (value: number) => `${integer.format(value)} mm`
export const mmSigned = (value: number) => `${signed.format(value)} mm`
export const pct = (value: number) => `${integer.format(value)} %`
export const index = (value: number) => twoDecimals.format(value)
export const num = (value: number) => decimal.format(value)

const dateShort = new Intl.DateTimeFormat('pl-PL', { day: 'numeric', month: 'short' })
const dateLong = new Intl.DateTimeFormat('pl-PL', { dateStyle: 'long' })
const dateTimeFmt = new Intl.DateTimeFormat('pl-PL', { dateStyle: 'medium', timeStyle: 'short' })
const monthName = new Intl.DateTimeFormat('pl-PL', { month: 'short' })

export const dayMonth = (iso: string) => dateShort.format(new Date(iso))
export const longDate = (iso: string) => dateLong.format(new Date(iso))
export const dateTime = (iso: string) => dateTimeFmt.format(new Date(iso))
export const month = (m: number) => monthName.format(new Date(2025, m - 1, 1))
