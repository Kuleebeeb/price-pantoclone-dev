// @vitest-environment jsdom
import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { Desk } from './Desk'
import { History } from './History'
import * as api from '@/lib/api'
import fixture from '@/test-fixtures/meta.json'
import { COA, EVERY_KEY, HISTORY, SAMPLE } from '@/lib/permissions'

/* ONE TICK PER SCREEN (server/api/permissions.py). The server refuses; the
 * screen only stops drawing what would be refused, so a person is not sent
 * into a 403. If the tabs were drawn from a fixed list these would fail. */

vi.mock('@/lib/api', async () => ({
  ...(await vi.importActual<typeof api>('@/lib/api')),
  getCustomers: vi.fn().mockResolvedValue({ rows: [] }),
  listCoas: vi.fn().mockResolvedValue({ rows: [] }),
  coaSources: vi.fn().mockResolvedValue({ rows: [] }),
  historySearch: vi.fn().mockResolvedValue({ rows: [], count_text: '' }),
}))

const meta = fixture as unknown as api.Meta
const as = (...permissions: string[]) =>
  ({ token: 't', expires_at: 9999999999, user: { id: 1, email: 'qc@test', full_name: 'QC', permissions } }) as api.Session

describe('the desk draws only the tabs this account holds', () => {
  it('a COA-only account sees the COA tab and nothing that prices', () => {
    render(<Desk meta={meta} session={as('pricing.sign_in', COA)} onSignOut={() => {}} />)
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual(['COA / Quality'])
    expect(screen.getByText('Certificate of Analysis (COA)')).toBeTruthy()
    expect(screen.queryByText('2. คำนวณราคาจริง')).toBeNull()
    expect(screen.queryByRole('button', { name: meta.labels!.buttons.calculate })).toBeNull()
  })

  it('every key draws all six tabs, in the CEO order', () => {
    render(<Desk meta={meta} session={as('pricing.sign_in', ...EVERY_KEY)} onSignOut={() => {}} />)
    expect(screen.getAllByRole('tab')).toHaveLength(6)
    expect(screen.getByText('2. คำนวณราคาจริง')).toBeTruthy()
  })

  it('the door alone says no screen is ticked, and where to ask', () => {
    render(<Desk meta={meta} session={as('pricing.sign_in')} onSignOut={() => {}} />)
    expect(screen.queryAllByRole('tab')).toHaveLength(0)
    expect(screen.getByRole('alert').textContent).toContain('PacOs')
  })
})

describe('history draws only the buttons this account may use', () => {
  it('reading history without delete, edit or drawing keeps only what reads', () => {
    render(
      <History labels={meta.labels} products={meta.products} customers={[]} onEdit={() => {}} onStatus={() => {}}
        can={(key) => key === HISTORY || key === SAMPLE} />,
    )
    expect(screen.queryByRole('button', { name: 'ลบรายการที่เลือก / Delete Selected' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'แก้ไขข้อมูล / Edit' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'ทำแบบอนุมัติ / Create Drawing' })).toBeNull()
    expect(screen.getByRole('button', { name: 'ทำใบตัวอย่าง / Create Sample' })).toBeTruthy()
  })
})
