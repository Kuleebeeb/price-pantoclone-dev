// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { blank, Desk } from './Desk'
import * as api from '@/lib/api'
import { EVERY_KEY } from '@/lib/permissions'
import fixture from '@/test-fixtures/meta.json'

vi.mock('@/lib/api', async () => ({
  ...await vi.importActual<typeof api>('@/lib/api'),
  getCustomers: vi.fn().mockResolvedValue({ rows: [] }), quotationForm: vi.fn(), saveQuotation: vi.fn(),
  calculate: vi.fn().mockResolvedValue({ display: {}, formulas: {} }),
}))
vi.mock('./History', () => ({ History: ({ onEdit }: { onEdit: (ref: string) => void }) => <button onClick={() => onEdit('QT-EDIT')}>Open saved quote</button> }))
const meta = fixture as unknown as api.Meta
const session: api.Session = { token: 'test', expires_at: 9999999999, user: { id: 1, email: 'qa@test', full_name: 'QA', permissions: EVERY_KEY } }
const returned = { quote_ref: 'QT-EDIT', version: 8, id: 1, created_at: '2026-10-08' }
const customerInput = () => screen.getAllByLabelText(meta.labels!.fields.customer).find(node => node.tagName === 'INPUT') as HTMLInputElement

beforeEach(() => {
  localStorage.clear(); vi.clearAllMocks()
  vi.spyOn(window, 'alert').mockImplementation(() => {})
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  vi.spyOn(window, 'scrollTo').mockImplementation(() => {})
  vi.mocked(api.quotationForm).mockResolvedValue({ quote_ref: 'QT-EDIT', version: 7,
    form: { ...blank(meta), customer: 'Saved customer', customer_code: 'CS01', width: '10', length: '20' }, ref_text: 'QT-EDIT', status: 'Loaded' })
  vi.mocked(api.saveQuotation).mockResolvedValue(returned)
})

async function openSaved() {
  render(<Desk meta={meta} session={session} onSignOut={() => {}} />)
  fireEvent.click(screen.getByRole('tab', { name: meta.labels!.tabs.history }))
  fireEvent.click(screen.getByRole('button', { name: 'Open saved quote' }))
  await screen.findByRole('button', { name: 'บันทึกแก้ไขรายการเดิม' })
}

describe('quotation same-reference edit and distinct revision', () => {
  it('updates the same reference with the loaded version and clears only after success', async () => {
    await openSaved()
    fireEvent.click(screen.getByRole('button', { name: 'บันทึกแก้ไขรายการเดิม' }))
    await waitFor(() => expect(api.saveQuotation).toHaveBeenCalledTimes(1))
    expect(api.saveQuotation).toHaveBeenCalledWith(expect.objectContaining({ update_ref: 'QT-EDIT', expected_version: 7, revised_from_ref: '', request_id: expect.any(String) }))
    await waitFor(() => expect(customerInput()).toHaveValue(''))
    expect(screen.queryByRole('button', { name: /Revision/ })).not.toBeInTheDocument()
  })

  it('creates an explicit linked revision without the in-place update/version fields', async () => {
    await openSaved()
    fireEvent.click(screen.getByRole('button', { name: /Revision/ }))
    await waitFor(() => expect(api.saveQuotation).toHaveBeenCalledTimes(1))
    const payload = vi.mocked(api.saveQuotation).mock.calls[0]![0]
    expect(payload.revised_from_ref).toBe('QT-EDIT')
    expect(payload.update_ref).toBe('')
    expect(payload.expected_version).toBeUndefined()
  })

  it('a version conflict retains the edited draft and the same retry request ID', async () => {
    vi.mocked(api.saveQuotation).mockRejectedValue(new Error('A newer version exists'))
    await openSaved()
    fireEvent.change(customerInput(), { target: { value: 'Unsaved customer' } })
    fireEvent.click(screen.getByRole('button', { name: 'บันทึกแก้ไขรายการเดิม' }))
    await waitFor(() => expect(window.alert).toHaveBeenCalledWith('A newer version exists'))
    expect(customerInput()).toHaveValue('Unsaved customer')
    const first = vi.mocked(api.saveQuotation).mock.calls[0]![0]
    fireEvent.click(screen.getByRole('button', { name: 'บันทึกแก้ไขรายการเดิม' }))
    await waitFor(() => expect(api.saveQuotation).toHaveBeenCalledTimes(2))
    expect(vi.mocked(api.saveQuotation).mock.calls[1]![0].request_id).toBe(first.request_id)
    expect(vi.mocked(api.saveQuotation).mock.calls[1]![0].expected_version).toBe(7)
  })

  it('cancelling the confirmation performs no calculation or write', async () => {
    await openSaved()
    vi.mocked(window.confirm).mockReturnValue(false)
    fireEvent.click(screen.getByRole('button', { name: 'บันทึกแก้ไขรายการเดิม' }))
    expect(api.calculate).not.toHaveBeenCalled()
    expect(api.saveQuotation).not.toHaveBeenCalled()
    expect(customerInput()).toHaveValue('Saved customer')
  })
})
