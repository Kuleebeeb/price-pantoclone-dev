// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { History } from './History'
import * as api from '@/lib/api'
import fixture from '@/test-fixtures/meta.json'

/* A quotation a COA or sample report was issued from cannot be deleted; the
 * server says which document holds it (409). The screen used to answer every
 * failed delete with "may already have been deleted" - wrong, and it hid the
 * one fact a person needs to act on. "May already be deleted" stays for 404. */

vi.mock('@/lib/api', async () => ({
  ...(await vi.importActual<typeof api>('@/lib/api')),
  historySearch: vi.fn(),
  deleteQuotation: vi.fn(),
}))

const meta = fixture as unknown as api.Meta
const ROW = { ref: 'QT-20260830-0001', date: '2026-08-30', customer_code: 'CSK', customer: 'CSK Plasatic Co.,Ltd' }
const USED = 'ลบไม่ได้ ใบเสนอราคานี้ถูกใช้ในเอกสาร COA-202608-0001 / Cannot delete: used by COA-202608-0001'

async function deleteTheRow() {
  render(<History labels={meta.labels} products={meta.products} customers={[]} onEdit={() => {}} onStatus={() => {}} />)
  await userEvent.click(await screen.findByText('CSK Plasatic Co.,Ltd'))
  await userEvent.click(screen.getByRole('button', { name: 'ลบรายการที่เลือก / Delete Selected' }))
}

describe('deleting a quotation from history', () => {
  beforeEach(() => {
    vi.mocked(api.historySearch).mockResolvedValue({ rows: [ROW], count_text: '1' } as Awaited<ReturnType<typeof api.historySearch>>)
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.spyOn(window, 'alert').mockImplementation(() => {})
  })
  afterEach(() => vi.restoreAllMocks())

  it('a quotation a COA uses: the alert names the COA', async () => {
    vi.mocked(api.deleteQuotation).mockRejectedValue(new api.ApiError(409, USED))
    await deleteTheRow()
    await waitFor(() => expect(window.alert).toHaveBeenCalledWith(USED))
  })

  it('a quotation that is gone: still "may already have been deleted"', async () => {
    vi.mocked(api.deleteQuotation).mockRejectedValue(new api.ApiError(404, 'not found'))
    await deleteTheRow()
    await waitFor(() => expect(window.alert).toHaveBeenCalledWith(meta.labels!.history.delete_missing))
  })
})
