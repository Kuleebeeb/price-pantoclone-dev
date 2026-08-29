import { describe, expect, it } from 'vitest'
import { perSideThickness } from './Drawing'

/* THE ONE SUM "COPY FROM PRICING" DOES.
 *
 * The pricing screen measures thickness per PAIR by default; the drawing card
 * asks per SIDE. The desktop halves on copy (app.py:2250-2251) - copied
 * unhalved, every wall on the sheet the customer signs would be double.
 */

describe('copying a thickness onto the drawing', () => {
  it('perSideThickness_pair_isHalved', () => {
    expect(perSideThickness('0.08', 'pair')).toBe('0.04')
  })

  it('perSideThickness_side_passesThrough', () => {
    expect(perSideThickness('0.05', 'side')).toBe('0.05')
  })

  it('perSideThickness_emptyBox_staysEmpty', () => {
    // Halving a blank would write "0" into a box nobody filled in.
    expect(perSideThickness('', 'pair')).toBe('')
  })
})
