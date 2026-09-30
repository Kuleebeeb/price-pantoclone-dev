// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SampleInspection } from './SampleInspection'
import * as api from '@/lib/api'

const source: api.SampleSource = {
  quote_ref: 'QT-LIM-1', line: 'QT-LIM-1 | CSK | CSK Plasatic Co.,Ltd | PE BAG 4 x 12 inch',
  customer: 'CSK Plasatic Co.,Ltd', customer_code: 'CSK', part_no: '4P677198-1', product: 'PE BAG 4 x 12 inch',
  size_text: '4 x 12 inch', width_mm: 101.6, length_mm: 304.8, thickness_mm: 0.16, thickness_mode: 'pair',
  product_key: 'flat', gusset_mm: 0, tolerance_width_mm: 10, tolerance_length_mm: 10, tolerance_thickness_mm: 0.01,
  width_original: { value: 4, unit: 'นิ้ว' }, length_original: { value: 12, unit: 'นิ้ว' },
}

vi.mock('@/lib/api', async () => ({
  ...(await vi.importActual<typeof api>('@/lib/api')),
  listSampleInspections: vi.fn().mockResolvedValue({ rows: [] }),
  sampleSources: vi.fn(),
}))

const type = (box: number, value: string) =>
  fireEvent.change(screen.getAllByRole('spinbutton')[box]!, { target: { value } })

beforeEach(() => {
  vi.mocked(api.sampleSources).mockResolvedValue({ rows: [source] })
})

describe('sample inspection limits on screen', () => {
  it('a reading exactly on every limit shows PASS (0.17 - 0.16 is 0.010000000000000009)', async () => {
    render(<SampleInspection initialQuoteRef="QT-LIM-1" />)
    await waitFor(() => expect(screen.getAllByRole('spinbutton')).toHaveLength(9))
    // rows: width, length, thickness; columns: sample 1..3
    type(0, '111.6')
    type(3, '294.8')
    type(6, '0.17')
    type(8, '0.15')
    await waitFor(() => expect(screen.getAllByText('PASS')).toHaveLength(4))
    expect(screen.queryByText('FAIL')).toBeNull()
  })

  it('a reading just past the limit still shows FAIL', async () => {
    render(<SampleInspection initialQuoteRef="QT-LIM-1" />)
    await waitFor(() => expect(screen.getAllByRole('spinbutton')).toHaveLength(9))
    type(6, '0.171')
    await waitFor(() => expect(screen.getByText('FAIL')).toBeTruthy())
  })
})
