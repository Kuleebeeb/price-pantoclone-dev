// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { SampleInspection } from './SampleInspection'
import { sampleReportHtml } from './SampleInspection.report'
import * as api from '@/lib/api'

const source: api.SampleSource = {
  quote_ref: 'QT-SNAPSHOT', quote_version: 7, line: 'QT-SNAPSHOT | Test customer', customer: 'Test customer', customer_code: 'TEST',
  part_no: 'PART-01', product: 'PE GUSSET BAG', product_key: 'gusset', size_text: '',
  width_mm: 150, length_mm: 1000, thickness_mm: .076, thickness_mode: 'pair', gusset_mm: 20,
  width_original: { value: 15, unit: 'ซม.' }, length_original: { value: 1, unit: 'เมตร' },
  thickness_original: { value: .076, unit: 'มม.' }, gusset_original: { value: 2, unit: 'ซม.' },
  tolerance_width_mm: 0, tolerance_length_mm: 10, tolerance_thickness_mm: .005,
  tolerance_gusset_left_mm: 1, tolerance_gusset_right_mm: 2,
}
const record: api.SampleInspectionRecord = {
  id: 27, report_no: 'SI-20261008-0001', quote_ref: source.quote_ref, revision: 3,
  customer: source.customer, product: source.product, source_snapshot: source, length_datum: 'opening_to_bottom',
  inspection_date: '2026-10-06', tolerance_width_mm: 0, tolerance_length_mm: 10, tolerance_thickness_mm: .005,
  tolerance_gusset_left_mm: 1, tolerance_gusset_right_mm: 2, overall_result: 'PASS',
  results_json: [{ width: 150, length: 1000, thickness: .076, gusset_left: 19, gusset_right: 22 }],
  remarks: '<customer note>\nSecond line', checked_by: 'Inspector', approved_by: 'Approver',
}
vi.mock('@/lib/api', async () => ({
  ...await vi.importActual<typeof api>('@/lib/api'),
  sampleSources: vi.fn(), listSampleInspections: vi.fn(), saveSampleInspection: vi.fn(), deleteSampleInspection: vi.fn(),
}))
const written = vi.fn()
const target = { document: { open: vi.fn(), write: written, close: vi.fn() }, focus: vi.fn(), close: vi.fn() }

beforeEach(() => {
  vi.clearAllMocks()
  vi.mocked(api.sampleSources).mockResolvedValue({ rows: [source] })
  vi.mocked(api.listSampleInspections).mockResolvedValue({ rows: [] })
  vi.mocked(api.saveSampleInspection).mockResolvedValue({ row: record })
  vi.spyOn(window, 'open').mockReturnValue(target as unknown as Window)
})

async function draw() {
  render(<SampleInspection initialQuoteRef={source.quote_ref} />)
  await waitFor(() => expect(screen.getAllByRole('spinbutton')).toHaveLength(15))
}

describe('saved sample reports', () => {
  it('Save persists the datum and adopts the returned immutable snapshot and revision', async () => {
    await draw()
    fireEvent.click(screen.getByRole('button', { name: /Opening to Bottom/ }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByText(`บันทึกแล้ว ${record.report_no}`)
    expect(api.saveSampleInspection).toHaveBeenLastCalledWith(expect.objectContaining({ length_datum: 'opening_to_bottom', expected_quote_version: 7, request_id: expect.any(String) }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.saveSampleInspection).toHaveBeenCalledTimes(2))
    expect(api.saveSampleInspection).toHaveBeenLastCalledWith(expect.objectContaining({ id: 27, expected_revision: 3, length_datum: 'opening_to_bottom' }))
    expect(vi.mocked(api.saveSampleInspection).mock.calls[1]![0].expected_quote_version).toBeUndefined()
    expect(screen.getByText('15 ซม. → 150 mm')).toBeInTheDocument()
  })

  it('refuses a new save if the selected source has no version', async () => {
    const { quote_version: _version, ...unversioned } = source
    vi.mocked(api.sampleSources).mockResolvedValue({ rows: [unversioned] })
    await draw()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByText(/Reload the source quotation before saving/)
    expect(api.saveSampleInspection).not.toHaveBeenCalled()
  })

  it('lets a new report reload the same quotation after a source-version conflict', async () => {
    vi.mocked(api.saveSampleInspection).mockRejectedValueOnce(new Error('Source changed; reload it'))
    await draw()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByText('Source changed; reload it')
    vi.mocked(api.sampleSources).mockResolvedValue({ rows: [{ ...source, quote_version: 8, line: 'QT-SNAPSHOT | Updated version' }] })
    fireEvent.change(screen.getByPlaceholderText('ค้นหา QT / ลูกค้า / Part No.'), { target: { value: 'QT-SNAPSHOT' } })
    fireEvent.click(await screen.findByRole('button', { name: 'QT-SNAPSHOT | Updated version' }))
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.saveSampleInspection).toHaveBeenCalledTimes(2))
    expect(vi.mocked(api.saveSampleInspection).mock.calls[1]![0].expected_quote_version).toBe(8)
  })

  it('Save & Print uses the server response, including measured values and both gussets', async () => {
    await draw()
    fireEvent.click(screen.getByRole('button', { name: /Save & Print/ }))
    await waitFor(() => expect(written).toHaveBeenCalledTimes(1))
    const html = written.mock.calls[0]![0] as string
    expect(html).toContain(record.report_no)
    expect(html).toContain('OPENING TO BOTTOM')
    expect(html).toContain('0.071 – 0.081')
    expect(html).toContain('Gusset Left')
    expect(html).toContain('Gusset Right')
    expect(html).toContain('<td>22</td>')
    expect(html).toContain('&lt;customer note&gt;')
    expect(html).toContain('Customer approval')
    expect(html).not.toContain('WORKSHEET')
  })

  it('historical Print never saves, changes the report number, or substitutes the current quotation', async () => {
    vi.mocked(api.listSampleInspections).mockResolvedValue({ rows: [{ ...record, report_no: 'SIR-LEGACY', length_datum: null }] })
    vi.mocked(api.sampleSources).mockResolvedValue({ rows: [{ ...source, width_mm: 999 }] })
    render(<SampleInspection />)
    fireEvent.click(await screen.findByRole('button', { name: 'Print' }))
    expect(api.saveSampleInspection).not.toHaveBeenCalled()
    const html = written.mock.calls[0]![0] as string
    expect(html).toContain('SIR-LEGACY')
    expect(html).toContain('NOT RECORDED')
    expect(html).toContain('<td>150</td>')
    expect(html).not.toContain('999')
    expect(html).not.toContain('000000000000')
  })

  it('reopening a legacy report preserves its missing datum and original units during Save', async () => {
    vi.mocked(api.listSampleInspections).mockResolvedValue({ rows: [{ ...record, length_datum: null }] })
    render(<SampleInspection />)
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    expect(screen.getByText('15 ซม. → 150 mm')).toBeInTheDocument()
    expect(screen.getByText(/Length reference was not recorded/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.saveSampleInspection).toHaveBeenCalled())
    expect(api.saveSampleInspection).toHaveBeenCalledWith(expect.objectContaining({ id: 27, expected_revision: 3, length_datum: null }))
  })

  it('a failed save retains the draft and reuses the request ID for the same retry', async () => {
    vi.mocked(api.saveSampleInspection).mockRejectedValueOnce(new Error('A newer revision exists')).mockResolvedValue({ row: record })
    await draw()
    fireEvent.change(screen.getByLabelText('Remarks'), { target: { value: 'Unsaved inspection' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByText('A newer revision exists')
    expect(screen.getByLabelText('Remarks')).toHaveValue('Unsaved inspection')
    const first = vi.mocked(api.saveSampleInspection).mock.calls[0]![0]
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.saveSampleInspection).toHaveBeenCalledTimes(2))
    expect(vi.mocked(api.saveSampleInspection).mock.calls[1]![0].request_id).toBe(first.request_id)
  })

  it('normalizes decimal strings from a saved record and still passes exact numeric limits', async () => {
    const legacy = { ...record, tolerance_width_mm: '0', tolerance_length_mm: '10', tolerance_thickness_mm: '0.01',
      tolerance_gusset_left_mm: '1', tolerance_gusset_right_mm: '2',
      source_snapshot: { ...source, thickness_mm: '0.16' },
      results_json: [{ width: '150', length: '1000', thickness: '0.17', gusset_left: '19', gusset_right: '22' }],
    } as unknown as api.SampleInspectionRecord
    vi.mocked(api.listSampleInspections).mockResolvedValue({ rows: [legacy] })
    render(<SampleInspection />)
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    expect(screen.queryByText('FAIL')).not.toBeInTheDocument()
    expect(screen.getAllByRole('spinbutton')[6]).toHaveValue(.17)
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.saveSampleInspection).toHaveBeenCalled())
    const payload = vi.mocked(api.saveSampleInspection).mock.calls[0]![0]
    expect(payload.tolerance_thickness_mm).toBe(.01)
    expect(payload.measurements[0]!.thickness).toBe(.17)
    expect(payload.tolerance_gusset_right_mm).toBe(2)
  })

  it('blocks every editable control and duplicate saves while a save is pending', async () => {
    let finish!: (value: { row: api.SampleInspectionRecord }) => void
    vi.mocked(api.saveSampleInspection).mockImplementation(() => new Promise(resolve => { finish = resolve }))
    await draw()
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    for (const label of ['Date', 'Remarks', 'Checked by', 'Approved by']) expect(screen.getByLabelText(label)).toBeDisabled()
    expect(screen.getByPlaceholderText('ค้นหา QT / ลูกค้า / Part No.')).toBeDisabled()
    expect(screen.getByRole('button', { name: /Opening to Bottom/ })).toBeDisabled()
    for (const input of screen.getAllByRole('spinbutton')) expect(input).toBeDisabled()
    fireEvent.change(screen.getByLabelText('Remarks'), { target: { value: 'Cannot replace pending draft' } })
    expect(screen.getByLabelText('Remarks')).toHaveValue('')
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(api.saveSampleInspection).toHaveBeenCalledTimes(1)
    await act(async () => finish({ row: record }))
    expect(screen.getByLabelText('Remarks')).toHaveValue(record.remarks)
    expect(screen.getByLabelText('Remarks')).not.toBeDisabled()
  })

  it('switching quotation clears the old report identity and measurements', async () => {
    const other = { ...source, quote_ref: 'QT-OTHER', line: 'QT-OTHER | Different source' }
    vi.mocked(api.listSampleInspections).mockResolvedValue({ rows: [record] })
    vi.mocked(api.sampleSources).mockResolvedValue({ rows: [source, other] })
    render(<SampleInspection />)
    fireEvent.click(await screen.findByRole('button', { name: 'Edit' }))
    fireEvent.click(await screen.findByRole('button', { name: other.line }))
    expect(screen.getAllByRole('spinbutton')[0]).toHaveValue(null)
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(api.saveSampleInspection).toHaveBeenCalled())
    const payload = vi.mocked(api.saveSampleInspection).mock.calls[0]![0]
    expect(payload.quote_ref).toBe('QT-OTHER')
    expect(payload.id).toBeUndefined()
    expect(payload.expected_revision).toBeUndefined()
  })

  it('keeps zero tolerance, original mixed units, thickness precision and escapes customer text', () => {
    const html = sampleReportHtml(record)
    expect(html).toContain('150 – 150 mm')
    expect(html).toContain('15 ซม. × 1 เมตร')
    expect(html).toContain('0.071 – 0.081')
    expect(html).toContain('0.038 มม.')
    expect(html).toContain('&lt;customer note&gt;')
    expect(html).not.toContain('<customer note>')
    expect(html).not.toContain('NaN')
  })
})
