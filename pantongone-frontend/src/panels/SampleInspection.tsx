import { useEffect, useRef, useState } from 'react'
import { deleteSampleInspection, listSampleInspections, sampleSources, saveSampleInspection, type SampleInspectionRecord, type SampleInspectionSave, type SampleMeasurement, type SampleSource } from '@/lib/api'
import { sampleReportHtml, sampleUnitFactor } from './SampleInspection.report'
import './SampleInspection.css'

const measurement = (): SampleMeasurement => ({ width: null, length: null, thickness: null, gusset_left: null, gusset_right: null })
const blank = (): SampleInspectionSave => ({ quote_ref: '', inspection_date: new Intl.DateTimeFormat('en-CA', { timeZone: 'Asia/Bangkok', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date()), length_datum: 'opening_to_seal', tolerance_width_mm: 0, tolerance_length_mm: 0, tolerance_thickness_mm: 0, tolerance_gusset_left_mm: 0, tolerance_gusset_right_mm: 0, measurements: [measurement(), measurement(), measurement()], remarks: '', checked_by: '', approved_by: '' })
const n = (value: string) => value === '' ? null : Number(value)
const s = (value: unknown) => value == null ? '' : String(value)
const errorText = (error: unknown) => error instanceof Error ? error.message : String(error)
const fixed = (value: number) => Number(value.toFixed(12)).toString()
const limit = (nominal: number, tolerance: number) => `${fixed(nominal - tolerance)} – ${fixed(nominal + tolerance)}`
const pass = (value: number | null, nominal: number, tolerance: number) => value == null ? 'WAITING' : Math.abs(value - nominal) <= tolerance + 1e-9 ? 'PASS' : 'FAIL'

function formFromRecord(record: SampleInspectionRecord): SampleInspectionSave {
  return {
    id: record.id, expected_revision: Number(record.revision), quote_ref: record.quote_ref,
    inspection_date: record.inspection_date, length_datum: record.length_datum ?? null,
    tolerance_width_mm: Number(record.tolerance_width_mm), tolerance_length_mm: Number(record.tolerance_length_mm),
    tolerance_thickness_mm: Number(record.tolerance_thickness_mm),
    tolerance_gusset_left_mm: Number(record.tolerance_gusset_left_mm), tolerance_gusset_right_mm: Number(record.tolerance_gusset_right_mm),
    measurements: [0, 1, 2].map(index => {
      const held = record.results_json[index]
      const value = (key: keyof SampleMeasurement) => held?.[key] == null ? null : Number(held[key])
      return { width: value('width'), length: value('length'), thickness: value('thickness'), gusset_left: value('gusset_left'), gusset_right: value('gusset_right') }
    }),
    remarks: s(record.remarks), checked_by: s(record.checked_by), approved_by: s(record.approved_by),
  }
}

export function SampleInspection({ initialQuoteRef = '', onBack }: { initialQuoteRef?: string; onBack?: () => void }) {
  const [form, setForm] = useState(blank)
  const [source, setSource] = useState<SampleSource | null>(null)
  const [q, setQ] = useState('')
  const [sources, setSources] = useState<SampleSource[]>([])
  const [rows, setRows] = useState<SampleInspectionRecord[]>([])
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const pending = useRef(false)
  const attempt = useRef<{ body: string; requestId: string } | null>(null)
  const patch = (value: Partial<SampleInspectionSave>) => { if (!pending.current) setForm(previous => ({ ...previous, ...value })) }
  const load = () => listSampleInspections().then(result => setRows(result.rows)).catch(reason => setError(errorText(reason)))
  const pick = (next: SampleSource) => {
    if (pending.current || (source?.quote_ref === next.quote_ref && (form.id || source.quote_version === next.quote_version))) return
    setSource(next); setQ(next.line)
    setForm({ ...blank(), quote_ref: next.quote_ref, ...(next.quote_version !== undefined ? { expected_quote_version: next.quote_version } : {}), tolerance_width_mm: next.tolerance_width_mm,
      tolerance_length_mm: next.tolerance_length_mm, tolerance_thickness_mm: next.tolerance_thickness_mm,
      tolerance_gusset_left_mm: next.tolerance_gusset_left_mm ?? 0, tolerance_gusset_right_mm: next.tolerance_gusset_right_mm ?? 0 })
    attempt.current = null; setError('')
    setMessage(`ดึงข้อมูลจาก ${next.quote_ref} แล้ว กรุณากรอกค่าที่วัดได้จริง`)
  }
  useEffect(() => { void load() }, [])
  useEffect(() => {
    let cancelled = false
    const timer = window.setTimeout(() => {
      sampleSources(q).then(result => { if (!cancelled) setSources(result.rows) }).catch(reason => { if (!cancelled) setError(errorText(reason)) })
    }, 250)
    return () => { cancelled = true; window.clearTimeout(timer) }
  }, [q])
  useEffect(() => {
    if (!initialQuoteRef) return
    let cancelled = false
    sampleSources(initialQuoteRef).then(result => {
      if (cancelled) return
      const exact = result.rows.find(row => row.quote_ref === initialQuoteRef)
      setSources(result.rows)
      if (exact) pick(exact)
      else setError('ไม่พบรายการอ้างอิง / Quotation not found')
    }).catch(reason => { if (!cancelled) setError(errorText(reason)) })
    return () => { cancelled = true }
  }, [initialQuoteRef])
  const actual = (index: number, key: keyof SampleMeasurement, value: string) => patch({ measurements: form.measurements.map((row, current) => current === index ? { ...row, [key]: n(value) } : row) })
  const edit = (record: SampleInspectionRecord) => {
    if (pending.current) return
    setForm(formFromRecord(record)); setSource(record.source_snapshot); setQ(record.quote_ref)
    attempt.current = null; setMessage('เปิดเพื่อแก้ไขแล้ว'); setError('')
  }
  const reset = () => {
    if (pending.current) return
    setForm(blank()); setSource(null); setQ(''); setMessage(''); setError(''); attempt.current = null
  }
  const persist = async (): Promise<SampleInspectionRecord> => {
    if (!form.id && (!Number.isInteger(form.expected_quote_version) || Number(form.expected_quote_version) < 1)) {
      throw new Error('กรุณาเลือกใบเสนอราคาใหม่เพื่อโหลดรุ่นล่าสุด / Reload the source quotation before saving')
    }
    const body = JSON.stringify(form)
    if (attempt.current?.body !== body) attempt.current = { body, requestId: crypto.randomUUID() }
    const result = await saveSampleInspection({ ...form, request_id: attempt.current.requestId })
    attempt.current = null
    setForm(formFromRecord(result.row)); setSource(result.row.source_snapshot)
    setRows(previous => [result.row, ...previous.filter(row => row.id !== result.row.id)])
    setMessage(`บันทึกแล้ว ${result.row.report_no}`)
    return result.row
  }
  const writeReport = (target: Window, record: SampleInspectionRecord) => {
    target.document.open(); target.document.write(sampleReportHtml(record)); target.document.close(); target.focus()
  }
  const save = async () => {
    if (pending.current) return
    pending.current = true; setBusy(true); setError('')
    try { await persist() } catch (reason) { setError(errorText(reason)) } finally { pending.current = false; setBusy(false) }
  }
  const saveAndPrint = async () => {
    if (pending.current) return
    const target = window.open('', 'sample_print')
    if (!target) { setError('กรุณาอนุญาตหน้าต่างพิมพ์ก่อน / Allow the print window'); return }
    pending.current = true; setBusy(true); setError('')
    try { writeReport(target, await persist()) } catch (reason) { target.close(); setError(errorText(reason)) } finally { pending.current = false; setBusy(false) }
  }
  const print = (record: SampleInspectionRecord) => {
    const target = window.open('', 'sample_print')
    if (!target) { setError('กรุณาอนุญาตหน้าต่างพิมพ์ก่อน / Allow the print window'); return }
    writeReport(target, record)
  }
  const remove = async (id: number) => {
    if (pending.current || !confirm('ลบรายงานนี้หรือไม่?')) return
    pending.current = true; setBusy(true); setError('')
    try {
      await deleteSampleInspection(id)
      if (form.id === id) { setForm(blank()); setSource(null); setQ(''); attempt.current = null }
      setRows(previous => previous.filter(row => row.id !== id))
    } catch (reason) { setError(errorText(reason)) } finally { pending.current = false; setBusy(false) }
  }
  const factor = sampleUnitFactor
  const chars = source ? [
    ['Width','width',source.width_mm,form.tolerance_width_mm,source.width_original??{value:source.width_mm,unit:'มม.'},false],
    ['Length','length',source.length_mm,form.tolerance_length_mm,source.length_original??{value:source.length_mm,unit:'มม.'},false],
    ['Thickness','thickness',source.thickness_mm,form.tolerance_thickness_mm,source.thickness_original??{value:source.thickness_mm,unit:'มม.'},true],
    ...(source.product_key==='gusset'?[
      ['Gusset Left','gusset_left',source.gusset_mm,form.tolerance_gusset_left_mm,source.gusset_original??{value:source.gusset_mm,unit:'มม.'},false],
      ['Gusset Right','gusset_right',source.gusset_mm,form.tolerance_gusset_right_mm,source.gusset_original??{value:source.gusset_mm,unit:'มม.'},false],
    ]:[]),
  ] : []
 return <section className="sample"><div className="sample-head"><div><h2>Sample Inspection Report</h2><p>รายงานผลการตรวจสอบงานตัวอย่างก่อนส่งให้ลูกค้า</p></div><div><button type="button" disabled={busy} onClick={reset}>New</button><button type="button" className="desk-accent" disabled={busy} onClick={() => void save()}>Save</button><button type="button" className="print-blank" disabled={busy} onClick={() => void saveAndPrint()}>บันทึกและพิมพ์รายงาน / Save & Print</button><button type="button" disabled={busy} onClick={()=>onBack?.()}>Back / ย้อนกลับ</button></div></div>
 {source && form.length_datum === null && <p className="sample-notice">ยังไม่ระบุจุดวัดในรายงานเดิม / Length reference was not recorded</p>}<div className="datum-choice"><b>เลือกจุดวัดความยาว / Length Reference</b><button type="button" disabled={busy} className={form.length_datum==='opening_to_bottom'?'is-selected':''} onClick={()=>patch({length_datum:'opening_to_bottom'})}><input type="radio" tabIndex={-1} readOnly checked={form.length_datum==='opening_to_bottom'}/> ปากถุงถึงก้นถุง / Opening to Bottom</button><button type="button" disabled={busy} className={form.length_datum==='opening_to_seal'?'is-selected':''} onClick={()=>patch({length_datum:'opening_to_seal'})}><input type="radio" tabIndex={-1} readOnly checked={form.length_datum==='opening_to_seal'}/> ปากถุงถึงแนวซีล / Opening to Seal</button></div>
 <div className="sample-card"><h3>เลือกข้อมูลจากใบเสนอราคา</h3><input disabled={busy} className="wide" value={q} onChange={e=>setQ(e.target.value)} placeholder="ค้นหา QT / ลูกค้า / Part No."/><div className="choices">{sources.slice(0,6).map(x=><button key={x.quote_ref} disabled={busy} onClick={()=>pick(x)}>{x.line}</button>)}</div>{source&&<p><b>{source.customer}</b> • {source.product} • Part {source.part_no}</p>}</div>
 {source&&<div className="sample-card"><p><b>ลักษณะงานพิเศษต้นทาง:</b> {source.special_requirements||'—'}</p><div className="tol"><label>Date<input disabled={busy} type="date" value={form.inspection_date} onChange={e=>patch({inspection_date:e.target.value})}/></label><label>Width ± mm<input value={form.tolerance_width_mm} readOnly/></label><label>Length ± mm<input value={form.tolerance_length_mm} readOnly/></label><label>Thickness ± mm<input value={form.tolerance_thickness_mm} readOnly/></label>{source.product_key==='gusset'&&<><label>Left Gusset ± mm<input value={form.tolerance_gusset_left_mm} readOnly/></label><label>Right Gusset ± mm<input value={form.tolerance_gusset_right_mm} readOnly/></label></>}</div>
 <table><thead><tr><th>Characteristic</th><th>Nominal (Quoted → mm)</th><th>Specification limits (Quoted → mm)</th><th>Sample 1 (mm)</th><th>Sample 2 (mm)</th><th>Sample 3 (mm)</th></tr></thead><tbody>{chars.map(([name,key,nom,tol,original,isThickness])=>{const o=original as {value:number;unit:string};const ot=Number(tol)/factor(o.unit,Boolean(isThickness));return <tr key={String(key)}><td>{String(name)}</td><td>{o.value} {o.unit} → {Number(nom)} mm</td><td>{limit(o.value,ot)} {o.unit}<br/>→ {limit(Number(nom),Number(tol))} mm</td>{form.measurements.map((m,i)=>{const v=m[key as keyof SampleMeasurement] as number|null;return <td key={i}><input type="number" step="0.001" value={s(v)} disabled={busy} onChange={e=>actual(i,key as keyof SampleMeasurement,e.target.value)}/><span className={pass(v,Number(nom),Number(tol)).toLowerCase()}>{pass(v,Number(nom),Number(tol))}</span></td>})}</tr>})}</tbody></table><div className="tol"><label>Remarks<textarea disabled={busy} value={form.remarks} onChange={e=>patch({remarks:e.target.value})}/></label><label>Checked by<input disabled={busy} value={form.checked_by} onChange={e=>patch({checked_by:e.target.value})}/></label><label>Approved by<input disabled={busy} value={form.approved_by} onChange={e=>patch({approved_by:e.target.value})}/></label></div><p className="saved" role="status">{message}</p></div>}
 {error && <p role="alert" className="sample-error">{error}</p>}<div className="sample-card"><h3>รายงานที่บันทึกแล้ว</h3><table><thead><tr><th>Report No.</th><th>Customer / Product</th><th>Result</th><th>Actions</th></tr></thead><tbody>{rows.map(r=><tr key={r.id}><td>{r.report_no}</td><td>{r.customer}<br/>{r.product}</td><td>{r.overall_result||'WAITING'}</td><td><button disabled={busy} onClick={()=>edit(r)}>Edit</button> <button disabled={busy} onClick={()=>print(r)}>Print</button> <button disabled={busy} className="danger" onClick={()=>void remove(r.id)}>Delete</button></td></tr>)}</tbody></table></div></section>}
