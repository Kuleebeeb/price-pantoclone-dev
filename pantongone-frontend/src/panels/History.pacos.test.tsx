// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { History } from './History'
import * as api from '@/lib/api'
import fixture from '@/test-fixtures/meta.json'

/* TICK, PRESS, LAND IN PACOS.
 *
 * Bee, 28-08-2026: "Chọn nhiều hàng đã tính -> Bấm tạo báo giá -> Nhảy sang
 * PacOs". What is pinned: the button does nothing until something is ticked,
 * sends exactly the ticked references, follows the address PacOs hands back,
 * and shows the server's own two-language refusal rather than swallowing it.
 * Ticking must not disturb the desktop's single selected row.
 */

vi.mock('@/lib/api', async () => {
  const real = await vi.importActual<typeof api>('@/lib/api')
  return { ...real, historySearch: vi.fn(), pushToPacos: vi.fn() }
})

const labels = (fixture as unknown as api.Meta).labels
const historySearch = vi.mocked(api.historySearch)
const pushToPacos = vi.mocked(api.pushToPacos)

const rows = [
  { ref: 'ZZB/69-01', date: '2026-03-01', customer: 'DAIKIN', item: 'PLASTIC BAG PE' },
  { ref: 'ZZB/69-02', date: '2026-03-02', customer: 'DAIKIN', item: 'PLASTIC BAG PE' },
  { ref: 'ZZB/69-03', date: '2026-03-03', customer: 'HONDA', item: 'ZIPPER BAG' },
]

beforeEach(() => {
  historySearch.mockReset()
  pushToPacos.mockReset()
  historySearch.mockResolvedValue({ rows, count_text: '3 records' } as never)
})
afterEach(cleanup)

function draw(bridgeOn = true) {
  return render(
    <History labels={labels} products={{}} customers={[]} onEdit={vi.fn()} onStatus={vi.fn()} bridgeOn={bridgeOn} />,
  )
}

describe('sending ticked prices to PacOs', () => {
  it('the button waits for a tick, then counts what was ticked', async () => {
    draw()
    await screen.findByText('ZZB/69-01')
    const button = screen.getByRole('button', { name: labels.bridge.button })
    expect(button).toBeDisabled()
    await userEvent.click(screen.getByLabelText(`${labels.bridge.check_col} ZZB/69-01`))
    await userEvent.click(screen.getByLabelText(`${labels.bridge.check_col} ZZB/69-02`))
    expect(screen.getByRole('button', { name: labels.bridge.button_count.split('{n}').join('2') })).toBeEnabled()
  })

  it('sends exactly the ticked references and follows the address PacOs hands back', async () => {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    pushToPacos.mockResolvedValue({ handoff_id: 'h-1', url: 'https://pacos.test/quotations/from-pantongone/h-1', lines: 2, customer: 'DAIKIN' })
    draw()
    await screen.findByText('ZZB/69-01')
    await userEvent.click(screen.getByLabelText(`${labels.bridge.check_col} ZZB/69-01`))
    await userEvent.click(screen.getByLabelText(`${labels.bridge.check_col} ZZB/69-02`))
    await userEvent.click(screen.getByRole('button', { name: /PacOs/ }))
    expect(pushToPacos).toHaveBeenCalledWith(['ZZB/69-01', 'ZZB/69-02'])
    await waitFor(() => expect(assign).toHaveBeenCalledWith('https://pacos.test/quotations/from-pantongone/h-1'))
    vi.unstubAllGlobals()
  })

  it("shows the server's own two-language refusal for rows of two customers", async () => {
    const alert = vi.spyOn(window, 'alert').mockImplementation(() => {})
    pushToPacos.mockRejectedValue(new api.ApiError(409, labels.bridge.mixed_customers))
    draw()
    await screen.findByText('ZZB/69-01')
    await userEvent.click(screen.getByLabelText(`${labels.bridge.check_col} ZZB/69-01`))
    await userEvent.click(screen.getByLabelText(`${labels.bridge.check_col} ZZB/69-03`))
    await userEvent.click(screen.getByRole('button', { name: /PacOs/ }))
    await waitFor(() => expect(alert).toHaveBeenCalledWith(labels.bridge.mixed_customers))
    expect(labels.bridge.mixed_customers).toMatch(/different customers/)
    expect(screen.getByRole('button', { name: /PacOs/ })).toBeEnabled()
    alert.mockRestore()
  })

  it('a tick does not select the row for Edit/Delete', async () => {
    draw()
    await screen.findByText('ZZB/69-01')
    await userEvent.click(screen.getByLabelText(`${labels.bridge.check_col} ZZB/69-01`))
    expect(screen.getByRole('button', { name: labels.history.buttons.edit })).toBeDisabled()
  })

  /* Until 14-09-2026 the button stayed, disabled, with the reason in a tooltip.
     PacOs D45 removed the bridge for good, so a button that can never be
     pressed is not drawn at all (the ticks stay: they are the tree's). */
  it('without a bridge on the server there is no PacOs button at all', async () => {
    draw(false)
    await screen.findByText('ZZB/69-01')
    expect(screen.queryByRole('button', { name: /PacOs/ })).toBeNull()
    expect(screen.getByRole('button', { name: labels.history.buttons.edit })).toBeDisabled()
  })
})
