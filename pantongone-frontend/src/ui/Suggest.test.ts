import { describe, expect, it } from 'vitest'
import { matches, type Suggestion } from './Suggest'

/* A suggestion list that returns the right names in the WRONG ORDER is a list
 * people stop reading after the first line - and then type the name by hand,
 * which is the whole thing this exists to prevent. */

const rows: Suggestion[] = [
  { customer: 'Honda Automobile (Thailand) Co.,Ltd', customer_code: 'HND-01', times: 210 },
  { customer: 'Daikin Industries (Thailand) Ltd.', customer_code: '', times: 180 },
  { customer: 'Nippon Honda Parts Co.,Ltd.', customer_code: '', times: 40 },
  { customer: 'Honda Logistics Asia Co.,Ltd.', customer_code: '', times: 12 },
  { customer: 'บริษัท โตโกะ เซอิ ซากุเซียว (ประเทศไทย) จำกัด', customer_code: 'TKS-9', times: 5 },
]

const names = (typed: string) => matches(rows, typed).map((r) => r.customer)

describe('the customer suggestions', () => {
  it('puts a name that STARTS with what was typed first', () => {
    const found = names('hon')
    expect(found[0]).toBe('Honda Automobile (Thailand) Co.,Ltd')
    // "Nippon Honda Parts" still matches - it is just not the first answer.
    expect(found).toContain('Nippon Honda Parts Co.,Ltd.')
    expect(found.indexOf('Nippon Honda Parts Co.,Ltd.')).toBeGreaterThan(
      found.indexOf('Honda Logistics Asia Co.,Ltd.'),
    )
  })

  it('does not care about case', () => {
    expect(names('HONDA')[0]).toBe('Honda Automobile (Thailand) Co.,Ltd')
  })

  it('finds a customer by the code, for people who work in codes all day', () => {
    expect(names('hnd')).toEqual(['Honda Automobile (Thailand) Co.,Ltd'])
  })

  it('finds Thai names the same way', () => {
    expect(names('โตโกะ')).toHaveLength(1)
  })

  it('offers everything when the box is empty', () => {
    // On a fresh record that is exactly when somebody wants to be shown who
    // exists, rather than made to guess a first letter.
    expect(matches(rows, '')).toHaveLength(rows.length)
  })

  it('gives nothing when nothing matches, so the list closes', () => {
    expect(names('zzzz')).toEqual([])
  })

  it('keeps the order it was given, which is by how often each is quoted', () => {
    // Re-sorting alphabetically here would bury the company somebody quotes
    // weekly behind whoever happens to start with "A".
    expect(names('co.,ltd')[0]).toBe('Honda Automobile (Thailand) Co.,Ltd')
  })

  it('is capped, so the list never covers the screen', () => {
    const many = Array.from({ length: 500 }, (_, i) => ({
      customer: `Customer ${i}`,
      customer_code: '',
      times: 1,
    }))
    expect(matches(many, 'customer', 8)).toHaveLength(8)
  })
})
