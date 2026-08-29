import { describe, expect, it } from 'vitest'
import { blank, toRequest } from './Desk'
import type { Form } from '@/lib/calc'

/* WHAT THIS HOLDS.
 *
 * The form is text and the request is numbers, and the conversion between them
 * is the one place on this side where a figure can be lost. Everything past it
 * is the server's arithmetic - the desktop program's own calculator.py - so a
 * fault here does not show up as a wrong answer. It shows up as a RIGHT answer
 * to a question nobody asked: the width somebody typed in inches sent as
 * centimetres, the deduction they switched off sent as ten per cent.
 *
 * The units travel as the Thai words the desktop uses. That is not decoration:
 * the server validates against exactly those strings, and "cm" would be
 * refused - which is the good outcome. The bad one is a unit that is accepted
 * and means something else.
 */

const form = (patch: Partial<Form>): Form => ({ ...blank(null), ...patch })

describe('the question the screen asks', () => {
  it('sends each box with the unit chosen beside it', () => {
    const request = toRequest(
      form({ width: '9', width_unit: 'นิ้ว', length: '14', length_unit: 'นิ้ว' }),
      null,
    )
    expect(request.width).toEqual({ value: 9, unit: 'นิ้ว' })
    expect(request.length).toEqual({ value: 14, unit: 'นิ้ว' })
  })

  it('measures the side fold in the same unit as the width', () => {
    // They are the same measurement of the same bag. Letting them differ is how
    // 400 + (125 + 125) becomes a bag half a metre wider than anybody drew.
    const request = toRequest(form({ width: '40', width_unit: 'ซม.', gusset: '12.5' }), null)
    expect(request.gusset.unit).toBe(request.width.unit)
  })

  it('carries the thickness basis, which is a factor of two', () => {
    const pair = toRequest(form({ thickness: '0.04', thickness_mode: 'pair' }), null)
    const side = toRequest(form({ thickness: '0.04', thickness_mode: 'side' }), null)
    expect(pair.thickness.mode).toBe('pair')
    expect(side.thickness.mode).toBe('side')
  })

  it('sends an empty box as nought rather than as text', () => {
    // The server refuses a missing figure by name. A blank arriving as "" would
    // be a 422 about a type instead of a sentence about a width.
    const request = toRequest(form({ width: '', thickness: '' }), null)
    expect(request.width.value).toBe(0)
    expect(request.thickness.value).toBe(0)
  })

  it('reads a number somebody typed with thousands separators', () => {
    expect(toRequest(form({ order_quantity: '10,000' }), null).order_quantity).toBe(10000)
  })

  it('says when the deduction is switched off, and keeps the figure', () => {
    /* Both halves travel. Sending nought per cent instead of "off" would look
     * the same today and stop looking the same the moment somebody switches it
     * back on and finds their 10 has become a 0. */
    const off = toRequest(form({ apply_deduction: false, deduction: '10' }), null)
    expect(off.apply_deduction).toBe(false)
    expect(off.deduction_percent).toBe(10)
  })

  it('never sends a weight formula of its own', () => {
    /* LAW P1. The default belongs to the product and lives with the formulas;
     * a screen that picked one would be a second opinion about how a bag is
     * weighed, and the one nobody maintains. */
    expect(toRequest(form({ width: '40' }), null).weight_formula).toBe('')
  })

  it('starts a new record on the desktop program\'s own defaults', () => {
    const fresh = blank(null)
    expect(fresh.density).toBe('0.92')
    expect(fresh.material_price).toBe('65')
    expect(fresh.deduction).toBe('10')
    expect(fresh.order_quantity).toBe('1000')
    expect(fresh.apply_deduction).toBe(true)
  })
})
