import { describe, expect, it } from 'vitest'
import { judge, limitText, limits, mmPerUnit, toUnit } from './inspection'

/* THE LINE THAT SAYS PASS OR FAIL.
 *
 * A sample inspection report goes to the customer with the goods. The
 * judgement is one comparison, and the comparison has exactly the trap
 * floating point sets for anybody comparing 0.17 against 0.16 ± 0.01.
 */

describe('judge', () => {
  it('judge_nothingMeasured_isWaitingNotAGuess', () => {
    expect(judge(null, 101.6, 10)).toBe('WAITING')
    expect(judge(undefined, 101.6, 10)).toBe('WAITING')
    expect(judge(Number.NaN, 101.6, 10)).toBe('WAITING')
  })

  it('judge_insideTolerance_passes', () => {
    expect(judge(101.6, 101.6, 10)).toBe('PASS')
    expect(judge(95, 101.6, 10)).toBe('PASS')
  })

  it('judge_exactlyOnTheLimit_passes', () => {
    expect(judge(111.6, 101.6, 10)).toBe('PASS')
    expect(judge(91.6, 101.6, 10)).toBe('PASS')
  })

  it('judge_thicknessOnTheLimit_passesDespiteFloatingPoint', () => {
    // 0.17 - 0.16 is 0.010000000000000009 in IEEE-754; the micrometer says 0.01.
    expect(judge(0.17, 0.16, 0.01)).toBe('PASS')
    expect(judge(0.15, 0.16, 0.01)).toBe('PASS')
  })

  it('judge_pastTheLimit_fails', () => {
    expect(judge(111.7, 101.6, 10)).toBe('FAIL')
    expect(judge(0.171, 0.16, 0.01)).toBe('FAIL')
  })
})

describe('specification limits', () => {
  it('limits_thickness_roundsToTheInputPrecision', () => {
    expect(limits(0.16, 0.01)).toEqual([0.15, 0.17])
    expect(limitText(0.16, 0.01)).toBe('0.15 – 0.17')
  })

  it('limits_inchWidthInMm_keepsOneDecimal', () => {
    expect(limitText(101.6, 10)).toBe('91.6 – 111.6')
  })

  it('limits_wholeNumbers_stayWhole', () => {
    expect(limitText(1700, 10)).toBe('1690 – 1710')
  })
})

describe('units the customer quotes in', () => {
  it('mmPerUnit_lengthTable', () => {
    expect(mmPerUnit('นิ้ว')).toBe(25.4)
    expect(mmPerUnit('ซม.')).toBe(10)
    expect(mmPerUnit('เมตร')).toBe(1000)
  })

  it('mmPerUnit_thicknessTable_hasMicronsNotMetres', () => {
    expect(mmPerUnit('ไมครอน', true)).toBe(0.001)
    expect(mmPerUnit('เมตร', true)).toBe(1)
  })

  it('mmPerUnit_unknownUnit_isMm', () => {
    expect(mmPerUnit('furlong')).toBe(1)
  })

  it('toUnit_tenMillimetres_isAboutFourTenthsOfAnInch', () => {
    expect(toUnit(10, 'นิ้ว')).toBeCloseTo(0.3937, 4)
    expect(toUnit(10, 'ซม.')).toBe(1)
  })
})
