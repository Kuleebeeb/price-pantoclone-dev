// @vitest-environment jsdom
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { History } from './History'
import * as api from '@/lib/api'
import fixture from '@/test-fixtures/meta.json'

/* THE BOOK ANSWERS WHEN ASKED, NOT PER KEYSTROKE.
 *
 * The desktop filters run on Enter or the Search button (app.py:2472) - and
 * so must these, because the book is 17,391 rows deep and a filter that fires
 * per keystroke is five queries where one was wanted. The other rule worth a
 * test: the three buttons that act on a selected row are DISABLED until a row
 * is actually selected - a Delete button that works with nothing selected is
 * a button that deletes whatever happens to be first.
 */

vi.mock('@/lib/api', async () => {
  const real = await vi.importActual<typeof api>('@/lib/api')
  return {
    ...real,
    historySearch: vi.fn(),
  }
})

const labels = (fixture as unknown as api.Meta).labels

const ROW = {
  ref: 'QT-20260827-0001',
  date: '2026-08-27',
  customer_code: 'ZE-1',
  customer: 'ZZ-EYE Co., Ltd.',
  sale_unit: 'ขายเป็นกิโลกรัม / Sell by kg',
  item: 'eye bag / EYE-01',
  product: 'ถุงพลาสติกเปิดปากตรง (Plastic Bag)',
  size: 'กว้าง/Width 45 ซม.',
  thickness: '0.08 มม. • ต่อคู่ / Per Pair',
  grams: '20.203',
  price_basis: 'b',
  calc_price: 'c',
  price_kg: '53.000',
  price: '—',
  pack: '2.0203',
  _product_reference: 'EYE-01',
  _item_description: 'eye bag',
}

function draw() {
  return render(
    <History
      labels={labels}
      products={(fixture as unknown as api.Meta).products}
      customers={[]}
      onEdit={() => {}}
      onStatus={() => {}}
    />,
  )
}

describe('the history filters and buttons', () => {
  beforeEach(() => {
    vi.mocked(api.historySearch)
      .mockReset()
      .mockResolvedValue({ rows: [ROW], count_text: '1 รายการ / records' })
  })

  it('typingAFilter_doesNotSearch_untilEnter', async () => {
    draw()
    await screen.findByText('1 รายการ / records')
    expect(api.historySearch).toHaveBeenCalledTimes(1)
    const size = screen.getByLabelText('ขนาด / Size')
    await userEvent.type(size, '45')
    expect(api.historySearch).toHaveBeenCalledTimes(1)
    await userEvent.type(size, '{Enter}')
    expect(api.historySearch).toHaveBeenCalledTimes(2)
  })

  it('theSearchButton_asksTheServerAgain', async () => {
    draw()
    await screen.findByText('1 รายการ / records')
    await userEvent.click(screen.getByRole('button', { name: 'ค้นหา / Search' }))
    expect(api.historySearch).toHaveBeenCalledTimes(2)
  })

  it('rowButtons_stayDisabled_untilARowIsChosen', async () => {
    draw()
    await screen.findByText('ZZ-EYE Co., Ltd.')
    const edit = screen.getByRole('button', { name: 'แก้ไขข้อมูล / Edit' })
    const del = screen.getByRole('button', { name: 'ลบรายการที่เลือก / Delete Selected' })
    expect(edit).toBeDisabled()
    expect(del).toBeDisabled()
    await userEvent.click(screen.getByText('ZZ-EYE Co., Ltd.'))
    expect(edit).toBeEnabled()
    expect(del).toBeEnabled()
  })

  it('clearFilters_emptiesTheBoxes_andSearchesOnce', async () => {
    draw()
    await screen.findByText('1 รายการ / records')
    const size = screen.getByLabelText('ขนาด / Size')
    await userEvent.type(size, '45')
    await userEvent.click(
      screen.getByRole('button', { name: 'ล้างตัวกรอง (ไม่ลบรายการ) / Clear Filters (does not delete)' }),
    )
    expect(size).toHaveValue('')
    expect(api.historySearch).toHaveBeenCalledTimes(2)
    expect(vi.mocked(api.historySearch).mock.calls.at(-1)?.[0].size).toBe('')
  })

  it('copies selected record and opens escaped A4 report without saving', async () => {
    const copy = vi.fn()
    const write = vi.fn()
    const popup = vi.spyOn(window, 'open').mockReturnValue({ document: {open:vi.fn(),write,close:vi.fn()} } as unknown as Window)
    render(<History labels={labels} products={{}} customers={[]} onEdit={()=>{}} onCopy={copy} onStatus={()=>{}} />)
    await screen.findByText(ROW.customer)
    await userEvent.click(screen.getByRole('checkbox'))
    await userEvent.click(screen.getByRole('button',{name:/Copy as New/}))
    expect(copy).toHaveBeenCalledWith(ROW.ref)
    await userEvent.click(screen.getByRole('button',{name:/Print Results/}))
    expect(write.mock.calls[0]?.[0]).toContain('size:A4 landscape')
    expect(write.mock.calls[0]?.[0]).toContain(ROW.customer)
    expect(write.mock.calls[0]?.[0]).toContain('น้ำหนักต่อใบ (กรัม)')
    expect(write.mock.calls[0]?.[0]).toContain('<td>20.20</td>')
    popup.mockRestore()
  })
  it('prints weight for piece sales too', async () => {
    vi.mocked(api.historySearch).mockResolvedValue({ rows: [{...ROW, sale_unit:'ใบ / piece', grams:'2.456'}], count_text:'1' })
    const write = vi.fn()
    const popup = vi.spyOn(window,'open').mockReturnValue({document:{open:vi.fn(),write,close:vi.fn()}} as unknown as Window)
    draw()
    await screen.findByText(ROW.customer)
    await userEvent.click(screen.getByRole('button',{name:/Print Results/}))
    expect(write.mock.calls[0]?.[0]).toContain('<td>2.46</td>')
    popup.mockRestore()
  })
})
