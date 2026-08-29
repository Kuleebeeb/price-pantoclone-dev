import { describe, expect, it } from 'vitest'
import { blank, deductionCaption, liveMarkup, toRequest } from './Desk'
import type { Form } from '@/lib/calc'
import type { Labels, Meta } from '@/lib/api'
import fixture from '@/test-fixtures/meta.json'

/* THE LIVE PIECES OF THE PRICING SCREEN.
 *
 * Two captions on this screen change while somebody is still typing - the
 * deduction caption over the adjusted-items tile and the auto-markup box -
 * and both have a desktop original whose behaviour is documented to the line
 * (app.py:589-609, 2784-2795). If either were painted on rather than
 * computed, these tests would be asserting a constant and the mid-typing
 * cases below could not pass.
 *
 * The fixture is generated FROM api/screen.py (see src/test-fixtures) - the
 * Thai in the assertions is the server's, not this file's.
 */

const labels = fixture.labels as unknown as Labels
const meta = fixture as unknown as Meta

const form = (patch: Partial<Form>): Form => ({ ...blank(null), ...patch })

describe('the deduction caption follows the typing', () => {
  it('deductionCaption_switchedOff_saysNoDeduction', () => {
    expect(deductionCaption(labels, form({ apply_deduction: false }))).toBe(
      'จำนวนชิ้นต่อกก. (ไม่หักเผื่อ) / Items per kg (no deduction)',
    )
  })

  it('deductionCaption_defaultTen_fillsTheTemplate', () => {
    expect(deductionCaption(labels, form({}))).toBe(
      'จำนวนชิ้นต่อกก.หลังหัก 10% / Items per kg after 10% deduction',
    )
  })

  it('deductionCaption_midTyping_showsWhatWasTyped', () => {
    // "1.." cannot be read as a number yet - somebody is mid-keystroke. The
    // desktop shows the raw text rather than blinking an error at a sentence
    // still being said (app.py:601-606). A parseable "1." reads as 1 there
    // too (Python float("1.") == JS Number("1.")), so that case normalises.
    expect(deductionCaption(labels, form({ deduction: '1..' }))).toContain('หลังหัก 1..%')
    expect(deductionCaption(labels, form({ deduction: '1.' }))).toContain('หลังหัก 1%')
  })

  it('deductionCaption_sevenPointFive_keepsTheDecimal', () => {
    expect(deductionCaption(labels, form({ deduction: '7.5' }))).toContain('หลังหัก 7.5%')
  })
})

describe('the auto markup is derived, never typed', () => {
  it('liveMarkup_basisBelowMaterial_goesNegative', () => {
    // 53 THB/kg over 65 THB/kg material: (53/65 - 1) x 100.
    expect(liveMarkup(form({ price_per_kg: '53', material_price: '65' }))).toBe('-18.46')
  })

  it('liveMarkup_missingEitherFigure_staysEmpty', () => {
    expect(liveMarkup(form({ price_per_kg: '', material_price: '65' }))).toBe('')
    expect(liveMarkup(form({ price_per_kg: '53', material_price: '0' }))).toBe('')
  })
})

describe('the question carries the new boxes', () => {
  it('toRequest_rollLength_travelsWithItsOwnUnit', () => {
    const request = toRequest(form({ sold_length: '300', sold_length_unit: 'เมตร' }), meta)
    expect(request.sold_length).toEqual({ value: 300, unit: 'เมตร' })
  })

  it('toRequest_coverGsm_comesFromTheBoxesNotAConstant', () => {
    // 120 and 80 used to be hard-coded in the request. The cover panel now
    // owns them, so a typed 150 must actually travel.
    const request = toRequest(form({ roof_gsm: '150', mesh_gsm: '90' }), meta)
    expect(request.roof_gsm).toBe(150)
    expect(request.mesh_gsm).toBe(90)
  })

  it('toRequest_coverDefaults_areTheDesktopsOwn', () => {
    const fresh = blank(null)
    expect(fresh.roof_gsm).toBe('120')
    expect(fresh.mesh_gsm).toBe('80')
    expect(fresh.sold_length_unit).toBe('เมตร')
  })
})
