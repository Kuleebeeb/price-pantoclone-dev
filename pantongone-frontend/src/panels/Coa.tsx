import { useEffect, useState } from 'react'
import {
  coaPrintHtml,
  coaSources,
  deleteCoa,
  listCoas,
  saveCoa,
  type CoaRecord,
  type CoaSave,
  type CoaSource,
} from '@/lib/api'
import './Coa.css'

const empty: CoaSave = {
  status: 'DRAFT',
  quote_ref: '',
  po_no: '',
  lot_no: '',
  production_date: null,
  inspection_date: null,
  issue_date: new Date().toISOString().slice(0, 10),
  quantity: '',
  material: 'POLYETHYLENE',
  color: '-',
  printing: '-',
  width_tolerance_mm: 10,
  length_tolerance_mm: 10,
  thickness_tolerance_mm: 0.01,
  actual_width_mm: null,
  actual_length_mm: null,
  actual_thickness_mm: null,
  result: '',
  remarks: '',
  checked_by: '',
  approved_by: '',
}
const num = (v: string) => (v.trim() === '' ? null : Number(v))
const str = (v: unknown) => (v == null ? '' : String(v))

export function Coa({ onBack }: { onBack?: () => void } = {}) {
  const [form, setForm] = useState<CoaSave>(empty),
    [q, setQ] = useState(''),
    [sources, setSources] = useState<CoaSource[]>([])
  const [source, setSource] = useState<CoaSource | null>(null),
    [rows, setRows] = useState<CoaRecord[]>([]),
    [message, setMessage] = useState('')
  const loadRows = () =>
    listCoas()
      .then((x) => setRows(x.rows))
      .catch(() => setRows([]))
  useEffect(() => {
    void loadRows()
  }, [])
  useEffect(() => {
    const t = setTimeout(
      () =>
        coaSources(q)
          .then((x) => setSources(x.rows))
          .catch(() => setSources([])),
      250,
    )
    return () => clearTimeout(t)
  }, [q])
  const patch = (p: Partial<CoaSave>) => setForm((f) => ({ ...f, ...p }))
  const pick = (s: CoaSource) => {
    setSource(s)
    patch({
      quote_ref: s.quote_ref,
      ...(s.tolerance_width_mm ? { width_tolerance_mm: s.tolerance_width_mm } : {}),
      ...(s.tolerance_length_mm ? { length_tolerance_mm: s.tolerance_length_mm } : {}),
      ...(s.tolerance_thickness_mm ? { thickness_tolerance_mm: s.tolerance_thickness_mm } : {}),
    })
    setQ(s.line)
  }
  const edit = (r: CoaRecord) => {
    setForm({
      ...empty,
      ...r,
      id: Number(r.id),
      production_date: str(r.production_date) || null,
      inspection_date: str(r.inspection_date) || null,
      issue_date: str(r.issue_date) || null,
      actual_width_mm: r.actual_width_mm == null ? null : Number(r.actual_width_mm),
      actual_length_mm: r.actual_length_mm == null ? null : Number(r.actual_length_mm),
      actual_thickness_mm: r.actual_thickness_mm == null ? null : Number(r.actual_thickness_mm),
    } as CoaSave)
    setSource(null)
    setQ(str(r.quote_ref))
    setMessage('เปิดเอกสารเพื่อแก้ไขแล้ว')
  }
  const save = async () => {
    try {
      const x = await saveCoa(form)
      setForm((f) => ({ ...f, id: Number(x.row.id) }))
      setMessage(`บันทึกแล้ว ${str(x.row.certificate_no) || '(DRAFT)'}`)
      loadRows()
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e))
    }
  }
  const print = async (id = form.id) => {
    if (!id) {
      alert('กรุณาบันทึกก่อนพิมพ์')
      return
    }
    const x = await coaPrintHtml(id)
    const w = window.open('', '_blank')
    if (w) {
      w.document.write(x.html)
      w.document.close()
    }
  }
  const remove = async (r: CoaRecord) => {
    if (r.status === 'FINAL') {
      alert('COA ที่ออกเลขที่แล้ว (FINAL) ลบไม่ได้ ให้ทำ Revision แทน')
      return
    }
    if (!confirm(`ลบ COA ${str(r.certificate_no) || '(DRAFT)'} ของ ${str(r.customer)} หรือไม่?`))
      return
    try {
      await deleteCoa(r.id)
      if (form.id === r.id) {
        setForm(empty)
        setSource(null)
        setQ('')
      }
      setMessage('ลบแล้ว')
      loadRows()
    } catch (e) {
      alert(e instanceof Error ? e.message : String(e))
    }
  }
  const field = (label: string, key: keyof CoaSave, type = 'text', readOnly = false) => (
    <label>
      <span>
        {label}
        {readOnly && <small> (จากใบเสนอราคา)</small>}
      </span>
      <input
        type={type}
        readOnly={readOnly}
        value={str(form[key])}
        onChange={(e) => patch({ [key]: e.target.value || null } as Partial<CoaSave>)}
      />
    </label>
  )
  return (
    <section className="coa">
      <div className="coa-title">
        <div>
          <h2>Certificate of Analysis (COA)</h2>
          <p>เลือกข้อมูลจากใบเสนอราคา แล้วกรอกผลตรวจจริงของแต่ละ Lot</p>
        </div>
        <div className="coa-actions">
          <button
            onClick={() => {
              setForm(empty)
              setSource(null)
              setQ('')
            }}
          >
            New
          </button>
          <button className="desk-accent" onClick={save}>
            Save
          </button>
          <button
            className="danger"
            disabled={!form.id || form.status === 'FINAL'}
            onClick={() => {
              const r = rows.find((x) => x.id === form.id)
              if (r) void remove(r)
            }}
          >
            Delete
          </button>
          <button onClick={() => print()}>Print</button>
          <button onClick={() => (onBack ? onBack() : history.back())}>Back</button>
        </div>
      </div>
      <div className="coa-card">
        <h3>1. ข้อมูลอ้างอิงจากใบเสนอราคา</h3>
        <label className="coa-wide">
          <span>ค้นหา QT / ลูกค้า / Part No. / รายการ</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="พิมพ์เพื่อค้นหา..."
          />
        </label>
        <div className="coa-source-list">
          {sources.slice(0, 8).map((s) => (
            <button key={s.quote_ref} onClick={() => pick(s)}>
              {s.line}
            </button>
          ))}
        </div>
        {(source || form.quote_ref) && (
          <div className="coa-source">
            <b>{source?.customer || str(rows.find((r) => r.id === form.id)?.customer)}</b>
            <span>Quotation: {form.quote_ref}</span>
            {source && (
              <>
                <span>Part: {source.part_no || '-'}</span>
                <span>{source.product}</span>
                <span>
                  {source.width_mm} × {source.length_mm} mm • {source.thickness_mm} mm/
                  {source.thickness_mode}
                </span>
                <span>
                  <b>ลักษณะงานพิเศษต้นทาง:</b> {source.special_requirements || '—'}
                </span>
              </>
            )}
          </div>
        )}
      </div>
      <div className="coa-card">
        <h3>2. ข้อมูล Lot และผลตรวจ</h3>
        <div className="coa-grid">
          {field('PO No.', 'po_no')}
          {field('Lot / Batch No.', 'lot_no')}
          {field('Quantity', 'quantity')}
          {field('Production Date', 'production_date', 'date')}
          {field('Inspection Date', 'inspection_date', 'date')}
          {field('Issue Date', 'issue_date', 'date')}
          {field('Material', 'material')}
          {field('Color', 'color')}
          {field('Printing', 'printing')}
          {field(
            'Width tolerance ± mm',
            'width_tolerance_mm',
            'number',
            !!source?.tolerance_width_mm,
          )}
          {field(
            'Length tolerance ± mm',
            'length_tolerance_mm',
            'number',
            !!source?.tolerance_length_mm,
          )}
          {field(
            'Thickness tolerance ± mm',
            'thickness_tolerance_mm',
            'number',
            !!source?.tolerance_thickness_mm,
          )}
          <label>
            <span>Actual Width (mm)</span>
            <input
              type="number"
              value={str(form.actual_width_mm)}
              onChange={(e) => patch({ actual_width_mm: num(e.target.value) })}
            />
          </label>
          <label>
            <span>Actual Length (mm)</span>
            <input
              type="number"
              value={str(form.actual_length_mm)}
              onChange={(e) => patch({ actual_length_mm: num(e.target.value) })}
            />
          </label>
          <label>
            <span>Actual Thickness</span>
            <input
              type="number"
              step="0.001"
              value={str(form.actual_thickness_mm)}
              onChange={(e) => patch({ actual_thickness_mm: num(e.target.value) })}
            />
          </label>
          <label>
            <span>Result</span>
            <select value={form.result} onChange={(e) => patch({ result: e.target.value })}>
              <option value="">— เลือก —</option>
              <option>PASS</option>
              <option>FAIL</option>
            </select>
          </label>
          {field('Checked by', 'checked_by')}
          {field('Approved by', 'approved_by')}
          <label>
            <span>Status</span>
            <select value={form.status} onChange={(e) => patch({ status: e.target.value })}>
              <option>DRAFT</option>
              <option>WAITING_FOR_INSPECTION</option>
              <option>WAITING_FOR_APPROVAL</option>
              <option>FINAL</option>
            </select>
          </label>
          <label className="coa-wide">
            <span>Remarks</span>
            <input value={form.remarks} onChange={(e) => patch({ remarks: e.target.value })} />
          </label>
        </div>
        <p className="coa-message">{message}</p>
      </div>
      <div className="coa-card">
        <h3>เอกสารที่บันทึกแล้ว</h3>
        <table>
          <thead>
            <tr>
              <th>Certificate No.</th>
              <th>Customer</th>
              <th>PO / Lot</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{str(r.certificate_no) || 'DRAFT'}</td>
                <td>
                  {str(r.customer)}
                  <br />
                  <small>{str(r.product)}</small>
                </td>
                <td>
                  {str(r.po_no)} / {str(r.lot_no)}
                </td>
                <td>{r.status}</td>
                <td>
                  <button onClick={() => edit(r)}>Edit</button>{' '}
                  <button onClick={() => print(r.id)}>Print</button>{' '}
                  <button
                    className="danger"
                    disabled={r.status === 'FINAL'}
                    title={r.status === 'FINAL' ? 'FINAL ลบไม่ได้ / cannot delete a FINAL COA' : ''}
                    onClick={() => remove(r)}
                  >
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
