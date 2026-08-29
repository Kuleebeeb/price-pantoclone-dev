// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Desk } from './Desk'
import * as api from '@/lib/api'
import fixture from '@/test-fixtures/meta.json'

/* THE THREE PRICE BOXES OBEY THE SALE BASIS.
 *
 * Selling by kg, the desktop draws ONE box - the kg box, reworded to "final
 * price" - and hides the calculated-piece pair (app.py:2748-2777). Selling by
 * piece, all three appear and the kg box goes back to being the basis. If the
 * boxes were painted on, switching the basis would change nothing and both of
 * these tests would fail.
 *
 * The third rule is the quiet one: CHANGING THE BASIS TURNS THE DEDUCTION
 * BACK ON (app.py:2744) - the desktop refuses to carry a switched-off
 * deduction across a change of sale unit.
 */

vi.mock('@/lib/api', async () => {
  const real = await vi.importActual<typeof api>('@/lib/api')
  return {
    ...real,
    getCustomers: vi.fn().mockResolvedValue({ rows: [] }),
  }
})

const meta = fixture as unknown as api.Meta
const session = {
  token: 't',
  expires_at: 9999999999,
  user: { id: 1, email: 'test@test.local', full_name: 'Tester' },
} as api.Session

function draw() {
  return render(<Desk meta={meta} session={session} onSignOut={() => {}} />)
}

describe('the price boxes and the sale basis', () => {
  it('sellingByKg_drawsOnlyTheKgBox_asFinalPrice', async () => {
    draw()
    expect(await screen.findByText(/Final selling price per kg \(Editable\)/)).toBeInTheDocument()
    expect(screen.queryByText(/Calculated price per piece \(Read-only\)/)).not.toBeInTheDocument()
    expect(screen.queryByText(/Final selling price per piece \(Editable\)/)).not.toBeInTheDocument()
  })

  it('sellingByPiece_drawsAllThree_andTheKgBoxBecomesTheBasis', async () => {
    const { container } = draw()
    const basis = container.querySelector('.desk-basis') as HTMLSelectElement
    await userEvent.selectOptions(basis, 'piece')
    expect(screen.getByText(/Calculated price per piece \(Read-only\)/)).toBeInTheDocument()
    expect(screen.getByText(/Final selling price per piece \(Editable\)/)).toBeInTheDocument()
    expect(screen.getByText(/Price basis per kg \(Editable\)/)).toBeInTheDocument()
    expect(screen.queryByText(/Final selling price per kg \(Editable\)/)).not.toBeInTheDocument()
  })

  it('changingTheBasis_turnsTheDeductionBackOn', async () => {
    const { container } = draw()
    const apply = screen.getByLabelText(/ใช้ค่าหัก \/ Apply/) as HTMLInputElement
    await userEvent.click(apply)
    expect(apply).not.toBeChecked()
    const basis = container.querySelector('.desk-basis') as HTMLSelectElement
    await userEvent.selectOptions(basis, 'piece')
    expect(screen.getByLabelText(/ใช้ค่าหัก \/ Apply/)).toBeChecked()
  })

  it('coverProduct_hidesThicknessAndItsMode', async () => {
    // The cover formula weighs roof and mesh by GSM; a thickness box left on
    // screen would be a question the calculation never reads (screen.py
    // FIELDS_BY_PRODUCT).
    const { container } = draw()
    await screen.findByText(/Final selling price per kg/)
    expect(screen.getByText('ความหนา * / Thickness')).toBeInTheDocument()
    const product = container.querySelector('.desk-row6 select') as HTMLSelectElement
    await userEvent.selectOptions(product, 'cover')
    expect(screen.queryByText('ความหนา * / Thickness')).not.toBeInTheDocument()
    expect(screen.queryByText(/Per Side\/Pair/)).not.toBeInTheDocument()
    expect(screen.getByText('ความสูง * / Height')).toBeInTheDocument()
  })
})
