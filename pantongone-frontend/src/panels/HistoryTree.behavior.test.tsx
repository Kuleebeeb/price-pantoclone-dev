// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { HistoryTree } from './HistoryTree'
import * as api from '@/lib/api'
import fixture from '@/test-fixtures/meta.json'

/* FOLDERS OPEN ONE LEVEL AT A TIME.
 *
 * The book is 28,000 rows; the tree must ask the server for a customer's
 * products only when that customer is opened, and for a product's quotes only
 * when that product is opened. A tree that fetched everything on mount would
 * be the flat table wearing carets.
 */

vi.mock('@/lib/api', async () => {
  const real = await vi.importActual<typeof api>('@/lib/api')
  return {
    ...real,
    historyTreeCustomers: vi.fn(),
    historyTreeProducts: vi.fn(),
    historyTreeRows: vi.fn(),
  }
})

const labels = (fixture as unknown as api.Meta).labels
const customers = vi.mocked(api.historyTreeCustomers)
const products = vi.mocked(api.historyTreeProducts)
const rows = vi.mocked(api.historyTreeRows)

beforeEach(() => {
  customers.mockReset()
  products.mockReset()
  rows.mockReset()
  customers.mockResolvedValue({
    groups: [
      { customer: 'ZZ-TREE ALPHA', customer_code: 'ZA', quotes: 4, products: 2, period: '2021-03-01 → 2026-04-01' },
      { customer: 'ZZ-TREE BETA', customer_code: '', quotes: 1, products: 1, period: '2026-05-01' },
    ],
    count_text: '2 ลูกค้า / customers · 5 รายการ / records',
  })
  products.mockResolvedValue({
    groups: [
      {
        product_name: 'PLASTIC BAG PE', size: 'กว้าง/Width 8 นิ้ว × ยาว/Length 12 นิ้ว', quotes: 3,
        period: '2021-03-01 → 2026-03-01', latest_price: '78.000', price_range: '65.000 – 78.000',
        sale_unit: 'ขายเป็นกิโลกรัม / Sell by kg',
      },
    ],
  })
  rows.mockResolvedValue({
    rows: [
      { ref: 'ZZT/69-01', date: '2026-03-01', price_kg: '78.000' },
      { ref: 'ZZT/66-01', date: '2023-03-01', price_kg: '71.000' },
      { ref: 'ZZT/64-01', date: '2021-03-01', price_kg: '65.000' },
    ],
  })
})

describe('the customer folder tree', () => {
  it('lists customers on mount and nothing deeper', async () => {
    const onCount = vi.fn()
    render(<HistoryTree labels={labels} filters={{}} onOpen={vi.fn()} onCount={onCount} />)
    expect(await screen.findByText('ZZ-TREE ALPHA')).toBeTruthy()
    expect(onCount).toHaveBeenCalledWith('2 ลูกค้า / customers · 5 รายการ / records')
    expect(products).not.toHaveBeenCalled()
    expect(rows).not.toHaveBeenCalled()
  })

  it('opening a customer fetches its product folders, opening a product fetches its quotes', async () => {
    const onOpen = vi.fn()
    render(<HistoryTree labels={labels} filters={{ customer: 'ZZ' }} onOpen={onOpen} onCount={vi.fn()} />)
    await userEvent.click(await screen.findByText('ZZ-TREE ALPHA'))
    expect(products).toHaveBeenCalledWith('ZZ-TREE ALPHA', { customer: 'ZZ' })
    const folder = await screen.findByText('PLASTIC BAG PE')
    expect(screen.getByText('65.000 – 78.000')).toBeTruthy()
    expect(rows).not.toHaveBeenCalled()

    await userEvent.click(folder)
    expect(rows).toHaveBeenCalledWith(
      'ZZ-TREE ALPHA', 'PLASTIC BAG PE', 'กว้าง/Width 8 นิ้ว × ยาว/Length 12 นิ้ว', { customer: 'ZZ' },
    )
    await waitFor(() => expect(screen.getByText('ZZT/64-01')).toBeTruthy())
    // newest first: the three prices read down the years (CEO 2026-09: 2 decimals)
    const cells = screen.getAllByText(/^(78|71|65)\.00$/).map((el) => el.textContent)
    expect(cells.indexOf('78.00')).toBeLessThan(cells.indexOf('65.00'))
  })

  it('a double-click on a quote opens the same Details window as the table', async () => {
    const onOpen = vi.fn()
    render(<HistoryTree labels={labels} filters={{}} onOpen={onOpen} onCount={vi.fn()} />)
    await userEvent.click(await screen.findByText('ZZ-TREE ALPHA'))
    await userEvent.click(await screen.findByText('PLASTIC BAG PE'))
    await userEvent.dblClick(await screen.findByText('ZZT/66-01'))
    expect(onOpen).toHaveBeenCalledWith('ZZT/66-01')
  })

  it('a folder opened under old filters closes when the filters change', async () => {
    const { rerender } = render(<HistoryTree labels={labels} filters={{}} onOpen={vi.fn()} onCount={vi.fn()} />)
    await userEvent.click(await screen.findByText('ZZ-TREE ALPHA'))
    expect(await screen.findByText('PLASTIC BAG PE')).toBeTruthy()
    rerender(<HistoryTree labels={labels} filters={{ date_from: '2026-01-01' }} onOpen={vi.fn()} onCount={vi.fn()} />)
    await waitFor(() => expect(screen.queryByText('PLASTIC BAG PE')).toBeNull())
    expect(customers).toHaveBeenCalledTimes(2)
  })
})
