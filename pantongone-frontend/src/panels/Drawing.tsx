import { useEffect, useState } from 'react'
import {
  drawingHtml,
  drawingRegister,
  getDrawing,
  saveDrawing,
  planningSources,
  quotationForm,
  type SourceRow,
  type Customer,
  type Labels,
  type Meta,
} from '@/lib/api'
import { orderedProducts, type DrawingRequest, type Form, type ProductKey } from '@/lib/calc'
import { Suggest } from '@/ui/Suggest'
import './Drawing.css'

/* THE SHEET THE CUSTOMER SIGNS - app.py _build_drawing (1876-2135), v1.7.1.
 *
 * Four cards: the document header, the dimensions with their tolerances, the
 * extra features, and the SAVED REGISTER - a drawing is saved into the same
 * table the desktop syncs into, and the DFA- number is issued only on save,
 * by one SQL statement on the server.
 *
 * The picture itself is drawn by the SERVER, from the desktop program's own
 * drawing.py - the same file, copied whole into core/. Preview opens the
 * finished printable page, exactly as the desktop opens it in a browser.
 */

type Props = {
  labels: Labels
  /** The pricing form - "Copy from Pricing" reads it, nothing else does. */
  form: Form
  meta: Meta | null
  customers: Customer[]
  initialQuoteRef?: string
}

type Sheet = {
  doc_no: string
  quote_ref: string
  date: string
  revision: string
  customer: string
  customer_code: string
  title: string
  part_no: string
  material: string
  color: string
  printing: string
  product_key: ProductKey
  length_datum: 'opening_to_seal' | 'opening_to_bottom'
  display_unit: 'mm' | 'inch'
  width: string
  width_unit: string
  length: string
  length_unit: string
  height: string
  height_unit: string
  gusset: string
  gusset_unit: string
  thickness: string
  thickness_unit: string
  tol_lo: string
  tol_hi: string
  tol_thickness: string
  holes_count: string
  holes_dia: string
  label_w: string
  label_h: string
  extra_notes: string
}

function todayLocal(): string {
  const now = new Date()
  const year = now.getFullYear()
  const month = String(now.getMonth() + 1).padStart(2, '0')
  const day = String(now.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

/* The desktop's own starting values (app.py:1883-1904). */
function blankSheet(): Sheet {
  return {
    doc_no: '',
    quote_ref: '',
    date: todayLocal(),
    revision: 'A',
    customer: '',
    customer_code: '',
    title: '',
    part_no: '-',
    material: 'POLYETHYLENE',
    color: '-',
    printing: '-',
    product_key: 'flat',
    length_datum: 'opening_to_seal',
    display_unit: 'mm',
    width: '',
    width_unit: 'ซม.',
    length: '',
    length_unit: 'ซม.',
    height: '',
    height_unit: 'ซม.',
    gusset: '',
    gusset_unit: 'ซม.',
    thickness: '',
    thickness_unit: 'มม.',
    tol_lo: '-10',
    tol_hi: '10',
    tol_thickness: '0.005',
    holes_count: '0',
    holes_dia: '20-25',
    label_w: '0',
    label_h: '0',
    extra_notes: '',
  }
}

/* Which dimension boxes each product draws (app.py:2144-2160). */
const DRAWN: Record<string, string[]> = {
  flat: ['width', 'length'],
  sleeve: ['width', 'length'],
  gusset: ['width', 'length', 'gusset'],
  opaque: ['width', 'length'],
  roll: ['width', 'length'],
  cover: ['width', 'length', 'height'],
}

function n(raw: string): number {
  const v = Number(String(raw).replace(/,/g, '').trim())
  return Number.isFinite(v) ? v : 0
}

/* A pair thickness copied onto the drawing is HALVED into per-side, exactly as
 * the desktop halves it (app.py:2250-2251) - the drawing card asks per side,
 * and copying the combined figure unhalved would double every wall on the
 * sheet the customer signs. */
export function perSideThickness(thickness: string, mode: 'side' | 'pair'): string {
  const value = n(thickness)
  return mode === 'pair' && value > 0 ? String(value / 2) : thickness
}

function openSheet(html: string) {
  const w = window.open('', '_blank')
  if (!w) return
  w.document.open()
  w.document.write(html)
  w.document.close()
}

type Row = Record<string, string>

export function Drawing({ labels, form, meta, customers, initialQuoteRef = '' }: Props) {
  const words = labels.drawing
  const [sheet, setSheet] = useState<Sheet>(blankSheet)
  const [status, setStatus] = useState(words.status_idle)
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState<Row[]>([])
  const [selected, setSelected] = useState('')
  const [drawingView, setDrawingView] = useState<'2d' | '3d' | 'both'>('2d')
  const [quoteQuery, setQuoteQuery] = useState('')
  const [quoteRows, setQuoteRows] = useState<SourceRow[]>([])

  const set = (patch: Partial<Sheet>) => setSheet((s) => ({ ...s, ...patch }))
  const drawn = DRAWN[sheet.product_key] ?? ['width', 'length']
  const asksDatum = sheet.product_key === 'flat' || sheet.product_key === 'gusset'
  const colors = labels.section_colors
  /* The dimension units, WITHOUT the metre - the drawing card never offers it
   * (app.py DimensionField, include_meter=False). */
  const units = (meta?.dimension_units ?? []).filter((u) => u !== 'เมตร')

  function refreshRegister(q = query) {
    drawingRegister(q)
      .then((answer) => {
        setRows(answer.rows as Row[])
        setSelected('')
      })
      .catch(() => setRows([]))
  }

  useEffect(() => {
    refreshRegister('')
    // Loaded once when the tab opens, as the desktop does (app.py:2135).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const timer = window.setTimeout(() => {
      planningSources(quoteQuery).then((answer) => setQuoteRows(answer.rows)).catch(() => setQuoteRows([]))
    }, 250)
    return () => window.clearTimeout(timer)
  }, [quoteQuery])

  async function loadQuotation(quoteRef: string) {
    try {
      const answer = await quotationForm(quoteRef)
      const source = answer.form as unknown as Partial<Form>
      setSheet((current) => ({
        ...current,
        quote_ref: quoteRef,
        customer: source.customer ?? '', customer_code: source.customer_code ?? '',
        title: source.item_description ?? '', part_no: source.product_reference?.trim() || '-',
        product_key: source.product_key ?? 'flat', date: source.quote_date ?? current.date,
        width: source.width ?? '', width_unit: source.width_unit ?? 'ซม.',
        length: (source.product_key === 'roll' ? source.sold_length : source.length) ?? '', length_unit: (source.product_key === 'roll' ? source.sold_length_unit : source.length_unit) ?? 'ซม.',
        height: source.height ?? '', height_unit: source.length_unit ?? 'ซม.',
        gusset: source.gusset ?? '', gusset_unit: source.width_unit ?? 'ซม.',
        thickness: perSideThickness(source.thickness ?? '', source.thickness_mode ?? 'pair'),
        thickness_unit: source.thickness_unit ?? 'มม.',
        length_datum: source.length_reference?.includes('ก้น') ? 'opening_to_bottom' : 'opening_to_seal',
        tol_lo: source.tolerance_width ? String(-Math.abs(Number(source.tolerance_width))) : current.tol_lo,
        tol_hi: source.tolerance_width ? String(Math.abs(Number(source.tolerance_width))) : current.tol_hi,
        tol_thickness: source.tolerance_thickness ?? current.tol_thickness,
        extra_notes: source.special_requirements ?? '',
      }))
      setQuoteQuery(quoteRef)
      setStatus(`รับข้อมูลจากใบคำนวณราคา ${quoteRef} แล้ว / Quotation loaded`)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  useEffect(() => {
    if (initialQuoteRef) void loadQuotation(initialQuoteRef)
    // A new reference from Quote History intentionally reloads the drawing source.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQuoteRef])

  /* Copy from Pricing (app.py:2230-2267): the sizes are NOT retyped - a
   * drawing that says 400 mm for a bag priced at 420 is worse than no drawing.
   * A pair thickness is halved into per-side, as the desktop halves it. */
  function copyFromPricing() {
    const thickness = perSideThickness(form.thickness, form.thickness_mode)
    set({
      customer: form.customer,
      customer_code: form.customer_code,
      title: form.item_description,
      part_no: form.product_reference.trim() || '-',
      product_key: form.product_key,
      date: form.quote_date,
      length_datum: form.length_reference.includes('ซีล') ? 'opening_to_seal' : 'opening_to_bottom',
      width: form.width,
      width_unit: form.width_unit,
      length: form.product_key === 'roll' ? form.sold_length : form.length,
      length_unit: form.product_key === 'roll' ? form.sold_length_unit : form.length_unit,
      height: form.height,
      height_unit: form.length_unit,
      gusset: form.gusset,
      gusset_unit: form.width_unit,
      thickness,
      thickness_unit: form.thickness_unit,
    })
    setStatus(words.statuses.copied)
  }

  function toRequest(): DrawingRequest {
    return {
      product_key: sheet.product_key,
      doc_no: sheet.doc_no,
      customer: sheet.customer,
      customer_code: sheet.customer_code,
      title: sheet.title,
      part_no: sheet.part_no,
      revision: sheet.revision,
      date: sheet.date,
      material: sheet.material,
      color: sheet.color,
      printing: sheet.printing,
      width: { value: n(sheet.width), unit: sheet.width_unit },
      length: { value: n(sheet.length), unit: sheet.length_unit },
      height: { value: n(sheet.height), unit: sheet.height_unit },
      gusset: { value: n(sheet.gusset), unit: sheet.gusset_unit },
      thickness: { value: n(sheet.thickness), unit: sheet.thickness_unit, mode: 'side' },
      tol_dim_lo: n(sheet.tol_lo),
      tol_dim_hi: n(sheet.tol_hi),
      tol_thickness: n(sheet.tol_thickness),
      length_datum: asksDatum ? sheet.length_datum : '',
      display_unit: sheet.display_unit,
      drawing_view: asksDatum ? drawingView : '2d',
      holes_count: Math.round(n(sheet.holes_count)),
      holes_dia: sheet.holes_dia,
      label_w: n(sheet.label_w),
      label_h: n(sheet.label_h),
      extra_notes: sheet.extra_notes.split('\n').filter((line) => line.trim()),
    }
  }

  async function preview() {
    try {
      const answer = await drawingHtml(toRequest())
      openSheet(answer.html)
      setStatus(words.statuses.previewed)
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setStatus(words.statuses.cannot_build + message)
      window.alert(message)
    }
  }

  async function save() {
    try {
      const answer = await saveDrawing({
        doc_no: sheet.doc_no,
        quote_ref: sheet.quote_ref,
        drawing_date: sheet.date,
        revision: sheet.revision,
        customer: sheet.customer,
        customer_code: sheet.customer_code,
        title: sheet.title,
        part_no: sheet.part_no,
        product_key: sheet.product_key,
        length_datum: asksDatum ? sheet.length_datum : '',
        display_unit: sheet.display_unit,
        width: { value: n(sheet.width), unit: sheet.width_unit },
        length: { value: n(sheet.length), unit: sheet.length_unit },
        height: { value: n(sheet.height), unit: sheet.height_unit },
        gusset: { value: n(sheet.gusset), unit: sheet.gusset_unit },
        thickness: { value: n(sheet.thickness), unit: sheet.thickness_unit, mode: 'side' },
        material: sheet.material,
        color: sheet.color,
        printing: sheet.printing,
        tol_dim_lo: n(sheet.tol_lo),
        tol_dim_hi: n(sheet.tol_hi),
        tol_thickness: n(sheet.tol_thickness),
        holes_count: Math.round(n(sheet.holes_count)),
        holes_dia: sheet.holes_dia,
        label_w: n(sheet.label_w),
        label_h: n(sheet.label_h),
        extra_notes: sheet.extra_notes.split('\n').filter((line) => line.trim()),
      })
      set({ doc_no: answer.doc_no })
      setStatus(answer.status)
      refreshRegister()
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setStatus(words.statuses.cannot_save + message)
      window.alert(message)
    }
  }

  /* New Drawing (app.py:2346-2357): the number, the sizes and the notes reset;
   * the customer, the title and the material lines deliberately survive. */
  function reset() {
    set({
      doc_no: '',
      revision: 'A',
      date: todayLocal(),
      width: '',
      length: '',
      height: '',
      gusset: '',
      thickness: '',
      extra_notes: '',
    })
    setStatus(words.statuses.reset)
  }

  async function openSelected(docNo?: string) {
    const target = docNo ?? selected
    if (!target) {
      setStatus(words.statuses.select_row)
      return
    }
    try {
      const answer = await getDrawing(target)
      const f = answer.form
      setSheet((s) => ({
        ...s,
        doc_no: f.doc_no ?? '',
        quote_ref: f.quote_ref ?? '',
        date: f.date ?? s.date,
        revision: f.revision ?? 'A',
        customer: f.customer ?? '',
        customer_code: f.customer_code ?? '',
        title: f.title ?? '',
        part_no: f.part_no ?? '-',
        product_key: (f.product_key as ProductKey) ?? 'flat',
        length_datum:
          f.length_datum === 'opening_to_bottom' ? 'opening_to_bottom' : 'opening_to_seal',
        display_unit: f.display_unit === 'inch' ? 'inch' : 'mm',
        width: f.width ?? '',
        width_unit: 'มม.',
        length: f.length ?? '',
        length_unit: 'มม.',
        height: f.height ?? '',
        height_unit: 'มม.',
        gusset: f.gusset ?? '',
        gusset_unit: 'มม.',
        thickness: f.thickness ?? '',
        thickness_unit: 'มม.',
        material: f.material ?? 'POLYETHYLENE',
        color: f.color ?? '-',
        printing: f.printing ?? '-',
        tol_lo: f.tol_lo ?? '-10',
        tol_hi: f.tol_hi ?? '10',
        tol_thickness: f.tol_thickness ?? '0.005',
        holes_count: f.holes_count ?? '0',
        holes_dia: f.holes_dia ?? '',
        label_w: f.label_w ?? '0',
        label_h: f.label_h ?? '0',
        extra_notes: f.extra_notes ?? '',
      }))
      setStatus(words.statuses.opened.split('{doc}').join(target))
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  return (
    <section className="desk-tabbody">
      {/* The four-button action row and the tab's own amber status line
          (app.py:1907-1938). */}
      <div className="dw-bar">
        <button type="button" onClick={copyFromPricing}>
          {words.buttons.copy}
        </button>
        <button type="button" className="desk-accent" onClick={preview}>
          {words.buttons.preview}
        </button>
        <button type="button" onClick={save}>
          {words.buttons.save}
        </button>
        <button type="button" onClick={reset}>
          {words.buttons.new}
        </button>
      </div>
      <p className="desk-status dw-status">{status}</p>

      <div className="desk-card">
        <h2 className="desk-band" style={{ background: colors.source }}>
          อ้างอิงใบคำนวณราคา / Quotation Reference
        </h2>
        <label className="desk-box">
          <span className="desk-label">เลขใบคำนวณราคา ลูกค้า รหัส หรือรายการ / Quote No., Customer, Code or Item</span>
          <input value={quoteQuery} onChange={(e) => setQuoteQuery(e.target.value)} placeholder="QT-YYYYMMDD-NNNN" />
        </label>
        <div className="dw-quote-list">
          {quoteRows.slice(0, 8).map((row) => (
            <button type="button" key={row.quote_ref} onClick={() => loadQuotation(row.quote_ref)}>{row.line}</button>
          ))}
        </div>
      </div>

      {/* Card 1 - the document (app.py:1940-1979). */}
      <div className="desk-card">
        <h2 className="desk-band" style={{ background: colors.product }}>
          {words.sections.document}
        </h2>
        <div className="desk-grid">
          <div className="desk-box">
            <span className="desk-label">{words.fields.doc_no}</span>
            <output className="dw-docno">{sheet.doc_no || words.not_issued}</output>
          </div>
          <Box label={words.fields.date}>
            <input type="date" value={sheet.date} onChange={(e) => set({ date: e.target.value })} />
          </Box>
          <Box label={words.fields.revision}>
            <input value={sheet.revision} onChange={(e) => set({ revision: e.target.value })} />
          </Box>
          <Box label={words.fields.customer_code}>
            <input
              value={sheet.customer_code}
              onChange={(e) => set({ customer_code: e.target.value })}
            />
          </Box>
          <div className="desk-box">
            <span className="desk-label">{words.fields.customer}</span>
            <Suggest
              label={words.fields.customer}
              value={sheet.customer}
              onChange={(customer) => set({ customer })}
              onPick={(customer_code) => {
                if (customer_code) set({ customer_code })
              }}
              rows={customers}
            />
          </div>
          <Box label={words.fields.title}>
            <input value={sheet.title} onChange={(e) => set({ title: e.target.value })} />
          </Box>
          <Box label={words.fields.part_no}>
            <input value={sheet.part_no} onChange={(e) => set({ part_no: e.target.value })} />
          </Box>
          <Box label={words.fields.material}>
            <input value={sheet.material} onChange={(e) => set({ material: e.target.value })} />
          </Box>
          <Box label={words.fields.color}>
            <input value={sheet.color} onChange={(e) => set({ color: e.target.value })} />
          </Box>
          <Box label={words.fields.printing}>
            <input value={sheet.printing} onChange={(e) => set({ printing: e.target.value })} />
          </Box>
        </div>
        <p className="desk-mutednote">{words.notes.revision}</p>
      </div>

      {/* Card 2 - dimensions and tolerances (app.py:1981-2077). */}
      <div className="desk-card">
        <h2 className="desk-band" style={{ background: colors.spec }}>
          {words.sections.dimensions}
        </h2>
        <div className="desk-grid">
          <Box label={words.fields.product_type}>
            <select
              value={sheet.product_key}
              onChange={(e) => set({ product_key: e.target.value as ProductKey })}
            >
              {orderedProducts(meta?.products).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </Box>
          <Box label={words.fields.length_reference}>
            <select
              value={sheet.length_datum}
              disabled={!asksDatum}
              onChange={(e) =>
                set({ length_datum: e.target.value as 'opening_to_seal' | 'opening_to_bottom' })
              }
            >
              {Object.entries(meta?.length_references ?? {}).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </Box>
          <Box label={words.fields.display_unit}>
            <div>ตามหน่วยที่กรอก — กว้าง {sheet.width_unit} / ยาว {sheet.length_unit}</div>
          </Box>
          {asksDatum && <Box label="รูปสินค้า / มุมมองสำหรับดูและพิมพ์">
            <select value={drawingView} onChange={(e) => setDrawingView(e.target.value as '2d' | '3d' | 'both')}>
              <option value="2d">2 มิติ — แบบอ้างอิงขนาด</option>
              <option value="3d">3 มิติ — ภาพประกอบรูปทรง</option>
              <option value="both">แสดงทั้งสอง</option>
            </select>
            <small>ภาพ 3 มิติไม่ใช่มาตราส่วนจริง ใช้ตารางขนาดเป็นหลัก</small>
          </Box>}
          <Box label={words.fields.thickness_side}>
            <div className="desk-pair">
              <input
                value={sheet.thickness}
                onChange={(e) => set({ thickness: e.target.value })}
              />
              <select
                value={sheet.thickness_unit}
                onChange={(e) => set({ thickness_unit: e.target.value })}
              >
                {(meta?.thickness_units ?? []).map((u) => (
                  <option key={u}>{u}</option>
                ))}
              </select>
            </div>
          </Box>
        </div>
        <div className="desk-grid">
          {drawn.includes('width') && (
            <Box label={words.fields.width}>
              <div className="desk-pair">
                <input value={sheet.width} onChange={(e) => set({ width: e.target.value })} />
                <select
                  value={sheet.width_unit}
                  onChange={(e) => set({ width_unit: e.target.value })}
                >
                  {units.map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
              </div>
            </Box>
          )}
          {drawn.includes('length') && (
            <Box label={words.fields.length}>
              <div className="desk-pair">
                <input value={sheet.length} onChange={(e) => set({ length: e.target.value })} />
                <select
                  value={sheet.length_unit}
                  onChange={(e) => set({ length_unit: e.target.value })}
                >
                  {units.map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
              </div>
            </Box>
          )}
          {drawn.includes('height') && (
            <Box label={words.fields.height}>
              <div className="desk-pair">
                <input value={sheet.height} onChange={(e) => set({ height: e.target.value })} />
                <select
                  value={sheet.height_unit}
                  onChange={(e) => set({ height_unit: e.target.value })}
                >
                  {units.map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
              </div>
            </Box>
          )}
          {drawn.includes('gusset') && (
            <Box label={words.fields.gusset}>
              <div className="desk-pair">
                <input value={sheet.gusset} onChange={(e) => set({ gusset: e.target.value })} />
                <select
                  value={sheet.gusset_unit}
                  onChange={(e) => set({ gusset_unit: e.target.value })}
                >
                  {units.map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
              </div>
            </Box>
          )}
        </div>
        <div className="desk-grid">
          <Box label={words.fields.tol_lo}>
            <input value={sheet.tol_lo} onChange={(e) => set({ tol_lo: e.target.value })} />
          </Box>
          <Box label={words.fields.tol_hi}>
            <input value={sheet.tol_hi} onChange={(e) => set({ tol_hi: e.target.value })} />
          </Box>
          <Box label={words.fields.tol_thickness}>
            <input
              value={sheet.tol_thickness}
              onChange={(e) => set({ tol_thickness: e.target.value })}
            />
          </Box>
        </div>
        <p className="desk-mutednote">{words.notes.thickness}</p>
      </div>

      {/* Card 3 - features and notes (app.py:2079-2102). */}
      <div className="desk-card">
        <h2 className="desk-band" style={{ background: colors.quality }}>
          {words.sections.features}
        </h2>
        <div className="desk-grid">
          <Box label={words.fields.holes_count}>
            <input
              value={sheet.holes_count}
              onChange={(e) => set({ holes_count: e.target.value })}
            />
          </Box>
          <Box label={words.fields.holes_dia}>
            <input value={sheet.holes_dia} onChange={(e) => set({ holes_dia: e.target.value })} />
          </Box>
          <Box label={words.fields.label_w}>
            <input value={sheet.label_w} onChange={(e) => set({ label_w: e.target.value })} />
          </Box>
          <Box label={words.fields.label_h}>
            <input value={sheet.label_h} onChange={(e) => set({ label_h: e.target.value })} />
          </Box>
        </div>
        <label className="desk-box dw-notes">
          <span className="desk-label">ลักษณะพิเศษที่ลูกค้าอนุมัติ (พิมพ์ได้หลายข้อ บรรทัดละหนึ่งข้อ) / Approved Special Characteristics</span>
          <textarea
            rows={3}
            value={sheet.extra_notes}
            onChange={(e) => set({ extra_notes: e.target.value })}
          />
        </label>
        <p className="desk-mutednote">{words.notes.standard}</p>
      </div>

      {/* Card 4 - the saved register (app.py:2104-2132). */}
      <div className="desk-card">
        <h2 className="desk-band" style={{ background: colors.production }}>
          {words.sections.register}
        </h2>
        <div className="dw-search">
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') refreshRegister()
            }}
          />
          <button type="button" onClick={() => refreshRegister()}>
            {words.buttons.search}
          </button>
          <button type="button" onClick={() => openSelected()}>
            {words.buttons.open}
          </button>
        </div>
        <div className="desk-tablewrap dw-register">
          <table className="desk-table hx-table">
            <colgroup>
              {words.register_columns.map((column) => (
                <col key={column.key} style={{ width: column.width + 'px' }} />
              ))}
            </colgroup>
            <thead>
              <tr>
                {words.register_columns.map((column) => (
                  <th key={column.key}>{column.label}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr
                  key={row.doc_no}
                  className={row.doc_no === selected ? 'is-selected' : ''}
                  onClick={() => setSelected(row.doc_no ?? '')}
                  onDoubleClick={() => openSelected(row.doc_no)}
                >
                  {words.register_columns.map((column) => (
                    <td key={column.key}>{row[column.key]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  )
}

function Box({
  label,
  children,
}: {
  label: string
  children: React.ReactNode
}) {
  return (
    <label className="desk-box">
      <span className="desk-label dw-label">{label}</span>
      {children}
    </label>
  )
}
