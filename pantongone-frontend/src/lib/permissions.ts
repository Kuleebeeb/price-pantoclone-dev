import type { User } from './api'

/* The keys server/api/permissions.py checks, ticked per role in PacOs
 * (People > "Who is allowed to do what" > pricing). This file only decides
 * what to HIDE, so nobody is sent into a refusal; the server is what refuses
 * (LAW K1), and a button left showing by mistake still gets a 403. */
export const CALCULATE = 'pricing.calculate'
export const SAVE = 'pricing.save'
export const HISTORY = 'pricing.history'
export const DELETE = 'pricing.delete'
export const DRAWING = 'pricing.drawing'
export const SAMPLE = 'pricing.sample_inspection'
export const PLANNING = 'pricing.planning'
export const COA = 'pricing.coa'

/* Every screen key, as a local account or a CEO after PacOs 0138 holds them. */
export const EVERY_KEY = [CALCULATE, SAVE, HISTORY, DELETE, DRAWING, SAMPLE, PLANNING, COA]

export type Tab ='pricing' | 'sample' | 'planning' | 'drawing' | 'coa' | 'history'

/* The CEO's tab order, and the one key each tab needs. */
export const TABS: [Tab, string][] = [
  ['pricing', CALCULATE],
  ['sample', SAMPLE],
  ['drawing', DRAWING],
  ['planning', PLANNING],
  ['coa', COA],
  ['history', HISTORY],
]

export const can = (user: User, key: string) => (user.permissions ?? []).includes(key)

export const openTabs = (user: User): Tab[] => TABS.filter(([, key]) => can(user, key)).map(([id]) => id)
