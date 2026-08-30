/* Judging a measured sample against what was quoted.
 *
 * Pure functions, out of the panel on purpose: the one line that decides
 * PASS or FAIL must be testable without a browser, and it has a trap - in
 * floating point 0.17 - 0.16 is 0.010000000000000009, which a naive
 * `<= 0.01` calls FAIL for a bag that is exactly on its limit.
 */

export type Verdict = 'PASS' | 'FAIL' | 'WAITING'

/** mm in one unit of the length the customer quotes in. */
export const LENGTH_MM_PER_UNIT: Record<string, number> = {
  'มม.': 1,
  'ซม.': 10,
  นิ้ว: 25.4,
  เมตร: 1000,
}

/** Thickness has its own table: microns exist, metres do not. */
export const THICKNESS_MM_PER_UNIT: Record<string, number> = {
  'มม.': 1,
  'ซม.': 10,
  นิ้ว: 25.4,
  ไมครอน: 0.001,
}

/** An unknown unit is taken as mm - the server stores mm and only mm (LAW P11). */
export function mmPerUnit(unit: string, thickness = false): number {
  return (thickness ? THICKNESS_MM_PER_UNIT : LENGTH_MM_PER_UNIT)[unit] ?? 1
}

/** A figure in mm shown in the unit the customer quoted: 10 mm -> 0.3937 in. */
export function toUnit(mm: number, unit: string, thickness = false): number {
  return mm / mmPerUnit(unit, thickness)
}

/* A hair of slack so a value exactly on the limit passes, as it does on the
 * micrometer. 1e-9 mm is a millionth of a micron - nothing real lives there. */
const EPSILON = 1e-9

/** Inclusive on both limits. Nothing measured yet is WAITING, never a guess. */
export function judge(actual: number | null | undefined, nominal: number, tolerance: number): Verdict {
  if (actual == null || Number.isNaN(actual)) return 'WAITING'
  return Math.abs(actual - nominal) <= tolerance + EPSILON ? 'PASS' : 'FAIL'
}

export function limits(nominal: number, tolerance: number): [number, number] {
  const digits = Math.max(decimals(nominal), decimals(tolerance))
  return [round(nominal - tolerance, digits), round(nominal + tolerance, digits)]
}

/** "0.15 – 0.17", not "0.15000000000000002 – 0.17". */
export function limitText(nominal: number, tolerance: number): string {
  const [lo, hi] = limits(nominal, tolerance)
  return `${lo} – ${hi}`
}

function decimals(x: number): number {
  const text = String(x)
  const dot = text.indexOf('.')
  return dot < 0 ? 0 : text.length - dot - 1
}

function round(x: number, digits: number): number {
  const f = 10 ** digits
  return Math.round(x * f) / f
}
