// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Login } from './Login'
import * as api from '@/lib/api'

/* THE DOOR.
 *
 * The desktop program asks before it draws anything, and this must too. What is
 * checked here is not that a form exists - it is the two ways a sign-in screen
 * quietly betrays the person at it:
 *
 *   - swallowing the server's answer. "ลองผิดหลายครั้งเกินไป กรุณารอ 15 นาที"
 *     is the difference between waiting a quarter of an hour and retyping a
 *     password that was right all along. A screen that prints "sign-in failed"
 *     has thrown away the only part anybody can act on.
 *   - keeping the password in the box after a refusal, where the next person at
 *     that machine finds it.
 *
 * And a third, since the password may now be PacOs's: not saying WHICH
 * password the box wants.
 */

vi.mock('@/lib/api', async () => {
  const real = await vi.importActual<typeof api>('@/lib/api')
  return { ...real, signIn: vi.fn() }
})

const meta = {
  version: 'src-2026-08-27',
  products: {},
  length_references: {},
  dimension_units: [],
  thickness_units: [],
  default_weight_formulas: {},
  default_price_formula: '',
  formula_variables: {},
  labels: {
    app_title: 'โปรแกรมคำนวณราคาพลาสติก / Plastic Pricing',
    app_subtitle: 'ระยะที่ 1',
  },
} as unknown as api.Meta

describe('the sign-in screen', () => {
  beforeEach(() => {
    vi.mocked(api.signIn).mockReset()
  })

  it('prints the title the server sent, not one of its own', () => {
    render(<Login meta={meta} metaError="" onSignedIn={() => {}} />)
    expect(screen.getByText('โปรแกรมคำนวณราคาพลาสติก / Plastic Pricing')).toBeInTheDocument()
  })

  it('shows the server\'s own sentence when it refuses', async () => {
    vi.mocked(api.signIn).mockRejectedValue(
      new api.ApiError(429, 'ลองผิดหลายครั้งเกินไป กรุณารอ 15 นาทีแล้วลองใหม่'),
    )
    render(<Login meta={meta} metaError="" onSignedIn={() => {}} />)
    await userEvent.type(screen.getByLabelText('อีเมล / Email'), 'admin')
    await userEvent.type(screen.getByLabelText('รหัสผ่าน / Password'), 'wrong')
    await userEvent.click(screen.getByRole('button'))
    expect(await screen.findByText(/15 นาที/)).toBeInTheDocument()
  })

  it('clears the password after a refusal', async () => {
    vi.mocked(api.signIn).mockRejectedValue(new api.ApiError(401, 'ไม่ถูกต้อง / no match'))
    render(<Login meta={meta} metaError="" onSignedIn={() => {}} />)
    const box = screen.getByLabelText('รหัสผ่าน / Password')
    await userEvent.type(screen.getByLabelText('อีเมล / Email'), 'admin')
    await userEvent.type(box, 'wrong')
    await userEvent.click(screen.getByRole('button'))
    await screen.findByText(/no match/)
    expect(box).toHaveValue('')
  })

  it('does not ask the server at all when a box is empty', async () => {
    render(<Login meta={meta} metaError="" onSignedIn={() => {}} />)
    await userEvent.click(screen.getByRole('button'))
    expect(api.signIn).not.toHaveBeenCalled()
    expect(screen.getByText(/กรุณากรอกอีเมลและรหัสผ่าน/)).toBeInTheDocument()
  })

  it('says which host the password is about to be sent to', () => {
    // A password box that will not say who is receiving it is the shape of
    // every phishing page ever made.
    render(<Login meta={meta} metaError="" onSignedIn={() => {}} />)
    expect(screen.getByText(new RegExp(window.location.host))).toBeInTheDocument()
  })

  it('says the box wants the PacOs password when the server signs people in there', () => {
    const viaPacos = { ...meta, sign_in_with: 'pacos' } as api.Meta
    render(<Login meta={viaPacos} metaError="" onSignedIn={() => {}} />)
    expect(screen.getByText(/Sign in with your PacOs email and password/)).toBeInTheDocument()
    expect(screen.getByText(/ask the PacOs administrator/)).toBeInTheDocument()
  })

  it('does not mention PacOs at all when the server keeps its own accounts', () => {
    const local = { ...meta, sign_in_with: 'local' } as api.Meta
    render(<Login meta={local} metaError="" onSignedIn={() => {}} />)
    expect(screen.queryByText(/PacOs/)).toBeNull()
  })
})
