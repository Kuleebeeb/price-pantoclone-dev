// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { History } from './History'
import * as api from '@/lib/api'
import fixture from '@/test-fixtures/meta.json'

/* Delete moves a quotation to the trash, with a reason, and Restore brings it
 * back (CEO 02-10-2026). A quotation a COA or sample report was issued from
 * still cannot go: the server names the document (409) and the dialog shows
 * that sentence, not a guess. */

vi.mock('@/lib/api', async () => ({
  ...(await vi.importActual<typeof api>('@/lib/api')),
  historySearch: vi.fn(),
  deleteQuotation: vi.fn(),
  quotationTrash: vi.fn(),
  restoreQuotation: vi.fn(),
}))

const meta = fixture as unknown as api.Meta
const ROW = { ref: 'QT-20260830-0001', date: '2026-08-30', customer_code: 'CSK', customer: 'CSK Plasatic Co.,Ltd' }
const USED = 'ลบไม่ได้ ใบเสนอราคานี้ถูกใช้ในเอกสาร COA-202608-0001 / Cannot delete: used by COA-202608-0001'

async function openDeleteDialog() {
  render(<History labels={meta.labels} products={meta.products} customers={[]} onEdit={() => {}} onStatus={() => {}} />)
  await userEvent.click(await screen.findByText('CSK Plasatic Co.,Ltd'))
  await userEvent.click(screen.getByRole('button', { name: 'ย้ายรายการที่ไฮไลต์ไปถังขยะ' }))
}

async function fillAndConfirm() {
  await userEvent.type(screen.getByRole('textbox', { name: /เหตุผลที่ลบ/ }), 'ราคาผิด')
  await userEvent.type(screen.getByRole('textbox', { name: /ชื่อผู้ดำเนินการ/ }), 'Somchai')
  await userEvent.click(screen.getByRole('button', { name: 'ยืนยันย้ายไปถังขยะ' }))
}

describe('deleting a quotation from history', () => {
  beforeEach(() => {
    vi.mocked(api.historySearch).mockResolvedValue({ rows: [ROW], count_text: '1' } as Awaited<ReturnType<typeof api.historySearch>>)
    vi.mocked(api.quotationTrash).mockResolvedValue({ rows: [], reason_required: true })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.spyOn(window, 'alert').mockImplementation(() => {})
  })
  afterEach(() => vi.restoreAllMocks())

  it('nothing is sent until a reason and a name are typed', async () => {
    await openDeleteDialog()
    expect(screen.getByRole('button', { name: 'ยืนยันย้ายไปถังขยะ' })).toBeDisabled()
    expect(api.deleteQuotation).not.toHaveBeenCalled()
  })

  it('sends the reason and the typed name, then closes', async () => {
    vi.mocked(api.deleteQuotation).mockResolvedValue({ deleted: ROW.ref })
    await openDeleteDialog()
    await fillAndConfirm()
    await waitFor(() => expect(api.deleteQuotation).toHaveBeenCalledWith(ROW.ref, 'ราคาผิด', 'Somchai'))
    await waitFor(() => expect(screen.queryByRole('dialog', { name: 'เหตุผลก่อนลบ' })).toBeNull())
  })

  it('a quotation a COA uses: the dialog names the COA', async () => {
    vi.mocked(api.deleteQuotation).mockRejectedValue(new api.ApiError(409, USED))
    await openDeleteDialog()
    await fillAndConfirm()
    expect(await screen.findByRole('alert')).toHaveTextContent(USED)
  })

  it('the trash lists what was deleted and Restore brings it back', async () => {
    vi.mocked(api.quotationTrash).mockResolvedValue({
      rows: [{ ref: ROW.ref, reason: 'ราคาผิด', actor: 'Suporn (typed: Somchai)', time: '2026-10-02T10:00:00+07:00' }],
      reason_required: true,
    })
    vi.mocked(api.restoreQuotation).mockResolvedValue({ restored: ROW.ref })
    render(<History labels={meta.labels} products={meta.products} customers={[]} onEdit={() => {}} onStatus={() => {}} />)
    await userEvent.click(await screen.findByRole('button', { name: 'ถังขยะ / กู้คืนรายการ' }))
    expect(await screen.findByText('Suporn (typed: Somchai)')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'กู้คืน' }))
    await waitFor(() => expect(api.restoreQuotation).toHaveBeenCalledWith(ROW.ref))
  })

  it('no delete key: neither the delete nor the trash button is drawn', async () => {
    render(<History labels={meta.labels} products={meta.products} customers={[]} onEdit={() => {}} onStatus={() => {}}
      can={(key) => key !== 'pricing.delete'} />)
    await screen.findByText('CSK Plasatic Co.,Ltd')
    expect(screen.queryByRole('button', { name: 'ย้ายรายการที่ไฮไลต์ไปถังขยะ' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'ถังขยะ / กู้คืนรายการ' })).toBeNull()
  })
})
