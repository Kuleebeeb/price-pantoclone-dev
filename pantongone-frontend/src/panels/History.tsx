import { useEffect, useRef, useState } from 'react'
import {
  deleteQuotation,
  quotationTrash, restoreQuotation, type TrashRow,
  historySearch,
  pushToPacos,
  quotationDetails,
  relatedTable,
  type Customer,
  type Labels,
  type SearchParams,
} from '@/lib/api'
import { Suggest } from '@/ui/Suggest'
import { orderedProducts } from '@/lib/calc'
import { CALCULATE, DELETE, DRAWING, SAMPLE } from '@/lib/permissions'
import { HistoryTree } from './HistoryTree'
import './History.css'

const readableWidths: Record<string, number> = {
  ref: 280, date: 110, customer_code: 105, customer: 240,
  sale_unit: 100, item: 360, product: 150, size: 380,
  thickness: 135, grams: 95, price_basis: 110, calc_price: 110,
  price_kg: 100, price: 100, pack: 100, moq: 100,
}

/* THE BOOK, 17,391 QUOTATIONS DEEP - app.py _build_history (2425-2630).
 *
 * FILTERS RUN ON ENTER OR THE SEARCH BUTTON, NOT PER KEYSTROKE: that is how
 * the desktop behaves (app.py:2472), and a book this deep answering every
 * keystroke would also be five queries where one was wanted. Picking a
 * customer suggestion searches at once, as the desktop does (2467).
 *
 * Every cell arrives from the server already formatted - fifteen columns of
 * the desktop's own Thai, widths included. This file draws them and holds
 * none of it.
 */

type Props = {
  labels: Labels
  products: Record<string, string>
  customers: Customer[]
  onEdit: (quoteRef: string) => void
  onCopy?: (quoteRef: string) => void
  onCreateSample?: (quoteRef: string) => void
  onCreateDrawing?: (quoteRef: string) => void
  onStatus: (text: string) => void
  /** From /api/meta: the server has a key for PacOs. Without it the button
   *  stays, disabled, saying why - a button that vanishes is a feature
   *  nobody knows exists. */
  bridgeOn?: boolean
  /** Whether this account holds a key (lib/permissions.ts). A button the
   *  server would refuse is not drawn; leaving it out allows everything. */
  can?: (key: string) => boolean
}

function openSheet(html: string) {
  const w = window.open('', '_blank')
  if (!w) { window.alert('กรุณาอนุญาตป๊อปอัปเพื่อเปิดรายงานพิมพ์'); return }
  w.document.open()
  w.document.write(html)
  w.document.close()
}

type Row = { ref: string; [key: string]: string }

export function historyPrintHtml(rows: Row[]) {
  const escape = (value: string) => value.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!))
  const groups = new Map<string, Row[]>()
  rows.forEach(r => { const key = (r.customer ?? '').trim() || `ไม่ระบุบริษัท (${r.customer_code})`; groups.set(key, [...(groups.get(key) ?? []), r]) })
  const sheets = [...groups].map(([company, entries]) => {
    const rollOnly = entries.every(r => r.sale_unit === 'ม้วน / roll')
    const includesRoll = entries.some(r => r.sale_unit === 'ม้วน / roll')
    const columns: [string, string][] = [
      ['ref','เลขอ้างอิง / วันที่'],['item','รายการ / รหัสสินค้า'],['spec','ขนาด / ความหนา'],
      ['weight',rollOnly ? 'กก./ม้วน' : includesRoll ? 'น้ำหนัก / หน่วย' : 'น้ำหนักต่อใบ (กรัม)'],['sale_unit','หน่วยขาย'],
      ['calculated',rollOnly ? 'คำนวณ บาท/ม้วน' : 'คำนวณ บาท/ใบ หรือม้วน'],
      ['actual',rollOnly ? 'ขายจริง บาท/ม้วน' : 'บันทึกเดิม บาท/ใบ / ขายจริง บาท/ม้วน'],
      ['price_kg','ฐานราคา บาท/กก.'],['moq','MOQ']]
    if (includesRoll) columns.push(['roll_quantity','จำนวนม้วน'],['roll_total_price','ยอดรวม บาท'])
    const body=entries.map(r => {
      const roll=r.sale_unit === 'ม้วน / roll'
      const cells: Record<string,string> = {...r,
        ref:[r.ref,r.date,'รหัสลูกค้า: '+(r.customer_code || 'ไม่ระบุ')].join('\n'),
        item:[r.item,r.product].filter(Boolean).join('\n'),spec:[r.size,r.thickness].filter(Boolean).join('\n'),
        weight:roll ? r.roll_kg+' กก./ม้วน' : displayCell('grams',r.grams)+(includesRoll && r.grams ? ' กรัม/ใบ' : ''),
        calculated:roll ? (r.roll_price ?? '') : displayCell('calc_price',r.calc_price),
        actual:roll ? (r.roll_sale_price || 'ใช้ราคาคำนวณ') : displayCell('price',r.price)}
      return '<tr>'+columns.map(([key])=>'<td>'+escape(cells[key] || '')+'</td>').join('')+'</tr>'
    }).join('')
    return '<section><h1>PANTONG THAI PACK CO., LTD.</h1><h2>ประวัติราคาที่บันทึก — '+escape(company)+'</h2><p>'+entries.length+' รายการ · รวมฉบับแก้ไข · ไม่ใช่ใบเสนอราคาฉบับอนุมัติ</p><table><thead><tr>'+columns.map(([,label])=>'<th>'+label+'</th>').join('')+'</tr></thead><tbody>'+body+'</tbody></table><p>ราคาคำนวณต่อม้วน = น้ำหนักสุทธิ/ม้วน × ฐานราคา/กก. ไม่รวมแกน ไม่หักจำนวน 10%</p><p>ยอดรวมม้วน = ราคาขายจริง × จำนวนม้วน หากไม่ได้กรอกราคาขายจริง ใช้ราคาคำนวณ ไม่เปลี่ยนข้อมูลเดิมที่บันทึก</p><p>รายการขายเป็นใบใช้ค่าหักจำนวนที่บันทึก ช่องว่างหมายถึงไม่มีข้อมูล ราคาฐานต่อ กก. ไม่ใช่ต้นทุนวัตถุดิบ</p></section>'
  }).join('')
  return '<!doctype html><html lang="th"><meta charset="utf-8"><title>ประวัติราคาแยกบริษัท</title><style>@page{size:A4 landscape;margin:10mm}body{font:11px Tahoma,Arial,sans-serif;color:#000}h1{font-size:17px}h2{font-size:15px}nav{padding:12px;background:#eef4fc}button{padding:10px;margin-right:10px}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{border:1px solid #444;padding:5px;overflow-wrap:anywhere;white-space:pre-line}thead{display:table-header-group}tr{break-inside:avoid}section{break-after:page}section:last-child{break-after:auto}@media print{nav{display:none}}</style><nav><button onclick="window.close()">← กลับหน้าประวัติ</button><button onclick="window.print()">พิมพ์ / บันทึก PDF</button></nav>'+sheets+'</html>'
}

function printRows(rows: Row[]) {
  openSheet(historyPrintHtml(rows))
}

const twoDecimalColumns = new Set(['grams', 'calc_price', 'price_kg', 'price', 'price_piece', 'pack', 'pack_kg'])

function displayCell(key: string, value: string | undefined) {
  const text = value ?? ''
  if (!twoDecimalColumns.has(key)) return text
  const plain = text.replace(/,/g, '').trim()
  if (!/^-?\d+(?:\.\d+)?$/.test(plain)) return text
  return Number(plain).toFixed(2)
}

export function History({ labels, products, customers, onEdit, onCopy, onCreateSample, onCreateDrawing, onStatus, bridgeOn = false, can = () => true }: Props) {
  const [customer, setCustomer] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const [size, setSize] = useState('')
  const [item, setItem] = useState('')
  const [productKey, setProductKey] = useState('')
  const [sort, setSort] = useState('newest')
  const [rows, setRows] = useState<Row[]>([])
  const [countText, setCountText] = useState('')
  const [error, setError] = useState('')
  const [trash, setTrash] = useState<TrashRow[] | null>(null)
  const [deleting, setDeleting] = useState<Row | null>(null)
  const [deleteReason, setDeleteReason] = useState('')
  const [deleteActor, setDeleteActor] = useState('')
  const [trashBusy, setTrashBusy] = useState(false)
  const [trashError, setTrashError] = useState('')
  const [selected, setSelected] = useState('')
  /* The rows ticked for PacOs. A Set, because the question asked of it is
   * only ever "is this one in"; kept apart from `selected`, which is the
   * desktop's single highlighted row and drives Edit/Print/Delete. */
  const [picked, setPicked] = useState<Set<string>>(() => new Set())
  const [sending, setSending] = useState(false)
  const [details, setDetails] = useState<{ title: string; text: string } | null>(null)
  const [related, setRelated] = useState<{ title: string; rows: Row[] } | null>(null)
  /* Table (the desktop's flat book) or folders (customer > product > every
   * price). Both obey the same filters; the tree reloads when Search runs. */
  const [view, setView] = useState<'table' | 'tree'>('table')
  const [treeFilters, setTreeFilters] = useState<SearchParams>({})
  const inFlight = useRef<AbortController | null>(null)

  const words = labels.history
  const filters = labels.history_filters
  const bridge = labels.bridge

  function search(over: Partial<Record<'customer' | 'productKey' | 'sort' | 'item' | 'size' | 'dateFrom' | 'dateTo', string>> = {}) {
    inFlight.current?.abort()
    const ac = new AbortController()
    inFlight.current = ac
    const params: SearchParams = {
      customer: over.customer ?? customer,
      item: over.item ?? item,
      product_key: over.productKey ?? productKey,
      size: over.size ?? size,
      date_from: over.dateFrom ?? dateFrom,
      date_to: over.dateTo ?? dateTo,
      sort: over.sort ?? sort,
      limit: 500,
    }
    setTreeFilters(params)
    historySearch(params, ac.signal)
      .then((answer) => {
        if (ac.signal.aborted) return
        setRows(answer.rows as Row[])
        setCountText(answer.count_text)
        setError('')
        setSelected('')
        setPicked(new Set())
      })
      .catch((e: Error) => {
        if (ac.signal.aborted || e.name === 'AbortError') return
        setError(e.message)
      })
  }

  useEffect(() => {
    search()
    // Once, when the tab opens - after that the desktop's rule holds: Enter,
    // the Search button, or a picked suggestion.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  function clearFilters() {
    setCustomer('')
    setDateFrom('')
    setDateTo('')
    setSize('')
    setItem('')
    setProductKey('')
    setSort('newest')
    search({ customer: '', productKey: '', sort: 'newest', item: '', size: '', dateFrom: '', dateTo: '' })
  }

  const selectedRow = rows.find((r) => r.ref === selected) ?? null

  function needSelection(): Row | null {
    if (!selectedRow) {
      window.alert(words.select_first)
      return null
    }
    return selectedRow
  }

  async function showDetails(ref?: string) {
    const target = ref ?? needSelection()?.ref
    if (!target) return
    try {
      setDetails(await quotationDetails(target))
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  async function printSelected() {
    const row = needSelection()
    if (!row) return
    try {
      printRows([row])
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  async function deleteSelected() {
    const row = needSelection()
    if (!row) return
    setDeleting(row); setDeleteReason(''); setDeleteActor(''); setTrashError('')
  }

  async function confirmDelete() {
    if (!deleting || trashBusy || !deleteReason.trim() || !deleteActor.trim()) return
    setTrashBusy(true); setTrashError('')
    try {
      await deleteQuotation(deleting.ref, deleteReason.trim(), deleteActor.trim())
      onStatus('ย้าย '+deleting.ref+' ไปถังขยะแล้ว — กู้คืนได้')
      setDeleting(null); search()
    } catch (e) { setTrashError(e instanceof Error ? e.message : String(e)) }
    finally { setTrashBusy(false) }
  }

  async function showTrash() {
    try { setTrashError(''); setTrash((await quotationTrash()).rows) }
    catch (e) { window.alert(e instanceof Error ? e.message : String(e)) }
  }

  async function restore(ref: string) {
    if (trashBusy || !window.confirm('กู้คืนรายการ '+ref+' กลับหน้าประวัติหรือไม่?')) return
    setTrashBusy(true)
    try { await restoreQuotation(ref); await showTrash(); search(); onStatus('กู้คืน '+ref+' แล้ว') }
    catch (e) { setTrashError(e instanceof Error ? e.message : String(e)) }
    finally { setTrashBusy(false) }
  }

  async function showRelated() {
    const row = needSelection()
    if (!row) return
    try {
      const answer = await relatedTable({
        product_reference: row._product_reference ?? row.product ?? '',
        item_description: row._item_description ?? row.item ?? '',
        size_text: row.size ?? '',
      })
      if (!answer.rows.length) {
        window.alert(words.related_none)
        return
      }
      setRelated({ title: answer.title, rows: answer.rows as Row[] })
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  function togglePick(ref: string) {
    setSelected(ref)
    setPicked((was) => {
      const next = new Set(was)
      if (next.has(ref)) next.delete(ref)
      else next.add(ref)
      return next
    })
  }

  /* ONE press, ONE customer, then PacOs. The server refuses rows of two
   * customers and rows with no PacOs customer, in its own two-language
   * sentence - shown as it arrived, because that sentence names the row and
   * says what to do, and "error 409" says neither. */
  async function sendToPacos() {
    if (picked.size === 0) {
      window.alert(bridge.select_first)
      return
    }
    setSending(true)
    onStatus(bridge.sending)
    try {
      const answer = await pushToPacos([...picked])
      onStatus(bridge.sent.split('{n}').join(String(answer.lines)))
      window.location.assign(answer.url)
    } catch (e) {
      setSending(false)
      onStatus('')
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  const onEnter = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') search()
  }

  return (
    <section className="desk-card">
      <h2 className="desk-band" style={{ background: labels.section_colors.history }}>
        {words.section}
      </h2>

      {/* The filters, in the desktop's left-to-right order (app.py:2449-2496). */}
      <div className="hx-filters">
        <div className="desk-box hx-customer">
          <span className="desk-label">{filters.customer}</span>
          <Suggest
            label={filters.customer}
            value={customer}
            onChange={setCustomer}
            /* A picked suggestion searches at once (app.py:2467). The code is
             * not written anywhere - this filter matches name OR code. */
            rows={customers}
          />
        </div>
        <label className="desk-box">
          <span className="desk-label">{filters.date_from}</span>
          <input value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} onKeyDown={onEnter} />
        </label>
        <label className="desk-box">
          <span className="desk-label">{filters.date_to}</span>
          <input value={dateTo} onChange={(e) => setDateTo(e.target.value)} onKeyDown={onEnter} />
        </label>
        <label className="desk-box">
          <span className="desk-label">{filters.size}</span>
          <input value={size} onChange={(e) => setSize(e.target.value)} onKeyDown={onEnter} />
        </label>
        <label className="desk-box">
          <span className="desk-label">{filters.item}</span>
          <input value={item} onChange={(e) => setItem(e.target.value)} onKeyDown={onEnter} />
        </label>
        <label className="desk-box">
          <span className="desk-label">{filters.product_key}</span>
          <select value={productKey} onChange={(e) => setProductKey(e.target.value)}>
            <option value="">{filters.all_types}</option>
            {orderedProducts(products).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label className="desk-box">
          <span className="desk-label">{filters.sort}</span>
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            {labels.choices.sort.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="hx-searchrow">
        <button type="button" disabled={!rows.length} onClick={() => printRows(rows)}>พิมพ์ผลค้นหา A4 / Print Results</button>
        <span>กรอกชื่อบริษัทหรือรหัสสินค้า แล้วกดค้นหาก่อนพิมพ์ — พิมพ์เฉพาะรายการที่แสดง</span>
        <button type="button" onClick={() => search()}>
          {labels.buttons.search}
        </button>
        <button type="button" onClick={clearFilters}>
          {labels.buttons.clear_filters}
        </button>
      </div>

      <div className="hx-viewrow" role="group" aria-label={words.view_tree}>
        <button
          type="button"
          className={view === 'table' ? 'is-on' : ''}
          aria-pressed={view === 'table'}
          onClick={() => setView('table')}
        >
          {words.view_table}
        </button>
        <button
          type="button"
          className={view === 'tree' ? 'is-on' : ''}
          aria-pressed={view === 'tree'}
          onClick={() => setView('tree')}
        >
          {words.view_tree}
        </button>
        {view === 'tree' && <span className="hx-hint">{words.tree_hint}</span>}
      </div>

      {error && <p className="desk-status">{error}</p>}

      {view === 'tree' && (
        <HistoryTree
          labels={labels}
          filters={treeFilters}
          onOpen={(ref) => showDetails(ref)}
          onCount={setCountText}
          picked={picked}
          onPick={togglePick}
        />
      )}

      {view === 'table' && (
      <div className="desk-tablewrap hx-tablewrap">
        <table className="desk-table hx-table">
          <colgroup>
            <col style={{ width: '44px' }} />
            {labels.history_columns.map((column) => (
              <col key={column.key} style={{ width: (readableWidths[column.key] ?? column.width) + 'px' }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th className="hx-pick">{bridge.check_col}</th>
              {labels.history_columns.map((column) => (
                <th key={column.key}>{column.key === 'product' ? 'รหัสสินค้า / Part No.' : column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr
                key={row.ref}
                className={row.ref === selected ? 'is-selected' : ''}
                onClick={() => setSelected(row.ref)}
                onDoubleClick={() => showDetails(row.ref)}
              >
                {/* Ticking must not also select the row for Edit/Delete, and
                    a double-click on the box must not open Details. */}
                <td className="hx-pick" onClick={(e) => e.stopPropagation()} onDoubleClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    aria-label={`${bridge.check_col} ${row.ref}`}
                    checked={picked.has(row.ref)}
                    onChange={() => togglePick(row.ref)}
                  />
                </td>
                {labels.history_columns.map((column) => (
                  <td key={column.key}>
                    {column.key.startsWith('roll_') && row.sale_unit !== 'ม้วน / roll'
                      ? 'ไม่ใช้กับรายการนี้'
                      : displayCell(column.key, row[column.key]) || 'ยังไม่ระบุ'}
                    {column.key === 'size' && row._input_details && (
                      <details className="hx-input-details" onClick={e => e.stopPropagation()} onDoubleClick={e => e.stopPropagation()}>
                        <summary>ดูข้อมูลจากหน้าเสนอราคาทั้งหมด</summary>
                        <div>{row._input_details}</div>
                      </details>
                    )}
                  </td>
                ))}
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={labels.history_columns.length + 1} className="desk-empty">
                  {filters.empty}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      )}

      {/* The five buttons, and the count on the right (app.py:2593-2620). */}
      <div className="hx-actions">
        <button type="button" onClick={() => showDetails()}>
          {words.buttons.details}
        </button>
        {can(SAMPLE) && <button
          type="button"
          className="hx-sample"
          disabled={!selectedRow || !onCreateSample}
          onClick={() => selectedRow && onCreateSample?.(selectedRow.ref)}
        >
          ทำใบตัวอย่าง / Create Sample
        </button>}
        {can(DRAWING) && <button
          type="button"
          className="hx-drawing"
          disabled={!selectedRow || !onCreateDrawing}
          onClick={() => selectedRow && onCreateDrawing?.(selectedRow.ref)}
        >
          ทำแบบอนุมัติ / Create Drawing
        </button>}
        {can(CALCULATE) && <button type="button" disabled={!selectedRow} onClick={() => selectedRow && onEdit(selectedRow.ref)}>
          แก้ไขข้อมูล / Edit
        </button>}
        {can(CALCULATE) && <button type="button" disabled={!selectedRow || !onCopy} onClick={() => selectedRow && onCopy?.(selectedRow.ref)}>คัดลอกเป็นรายการใหม่ / Copy as New</button>}
        <button type="button" disabled={!selectedRow} onClick={printSelected}>
          {words.buttons.print_selected}
        </button>
        {can(DELETE) && <button type="button" disabled={!selectedRow} onClick={deleteSelected}>
          ย้ายรายการที่ไฮไลต์ไปถังขยะ
        </button>}
        {can(DELETE) && <button type="button" onClick={showTrash}>ถังขยะ / กู้คืนรายการ</button>}
        <button type="button" onClick={showRelated}>
          {words.buttons.related}
        </button>
        <button
          type="button"
          className="hx-pacos"
          disabled={!bridgeOn || sending || picked.size === 0}
          title={bridgeOn ? '' : bridge.off}
          onClick={sendToPacos}
        >
          {picked.size > 0 ? bridge.button_count.split('{n}').join(String(picked.size)) : bridge.button}
        </button>
        <span className="hx-count">{countText}</span>
      </div>

      <p className="desk-mutednote">ดึงข้อมูลเก่ามาแก้ไข: เลือกรายการ แล้วบันทึกแก้ไขด้วยเลขเดิม ไม่เพิ่มรายการซ้ำ ข้อมูลก่อนแก้เก็บไว้ตรวจย้อนหลัง หรือเลือกออกฉบับแก้ไขใหม่ในหน้าป้อนข้อมูล</p>
      {deleting && <dialog open className="hx-dialog" aria-label="เหตุผลก่อนลบ">
        <h3>ย้ายรายการไปถังขยะ</h3>
        <p>{deleting.ref} — {deleting.customer} — {deleting.item}</p>
        <p>เก็บต้นฉบับและเอกสารอ้างอิงไว้ สามารถกู้คืนได้ ไม่ลบถาวร</p>
        <label>เหตุผลที่ลบ (ต้องกรอก)<textarea autoFocus maxLength={1000} value={deleteReason} disabled={trashBusy} onChange={e=>setDeleteReason(e.target.value)} style={{display:'block',width:'100%',minHeight:90}} /></label>
        <label>ชื่อผู้ดำเนินการ (ต้องกรอก เนื่องจากใช้บัญชี Demo ร่วมกัน)<input maxLength={200} value={deleteActor} disabled={trashBusy} onChange={e=>setDeleteActor(e.target.value)} /></label>
        {trashError && <p role="alert">{trashError}</p>}
        <div className="hx-close"><button disabled={trashBusy} onClick={()=>setDeleting(null)}>ยกเลิก</button><button disabled={trashBusy || !deleteReason.trim() || !deleteActor.trim()} onClick={confirmDelete}>ยืนยันย้ายไปถังขยะ</button></div>
      </dialog>}
      {trash && <dialog open className="hx-dialog is-wide" aria-label="ถังขยะ">
        <h3>ถังขยะ — เก็บประวัติไว้ ไม่ลบถาวร</h3>
        <p>ผู้ดำเนินการเป็นชื่อที่กรอกขณะใช้บัญชี Demo; รายการเก่าอาจไม่มีเหตุผลหรือชื่อ</p>
        {trashError && <p role="alert">{trashError}</p>}
        <div style={{maxHeight:'55vh',overflow:'auto'}}><table className="desk-table"><thead><tr><th>เลขรายการ</th><th>เหตุผล</th><th>ผู้ดำเนินการ</th><th>วันเวลาที่ลบ</th><th>กู้คืน</th></tr></thead><tbody>
          {trash.map(r=><tr key={r.ref}><td>{r.ref}</td><td style={{whiteSpace:'pre-wrap'}}>{r.reason}</td><td>{r.actor}</td><td>{r.time ? new Date(r.time).toLocaleString('th-TH') : 'ไม่ระบุ'}</td><td><button disabled={trashBusy} onClick={()=>restore(r.ref)}>กู้คืน</button></td></tr>)}
        </tbody></table>{!trash.length && <p>ไม่มีรายการในถังขยะ</p>}</div>
        <div className="hx-close"><button disabled={trashBusy} onClick={()=>setTrash(null)}>ปิด</button></div>
      </dialog>}

      {details && (
        <dialog
          className="hx-dialog"
          open
          aria-label={details.title}
        >
          <h3>{details.title}</h3>
          <pre className="hx-details">{details.text}</pre>
          <div className="hx-close">
            <button type="button" onClick={() => setDetails(null)}>
              {labels.formulas.close}
            </button>
          </div>
        </dialog>
      )}

      {related && (
        <dialog className="hx-dialog is-wide" open aria-label={related.title}>
          <h3>{related.title}</h3>
          <p className="hx-warn">{words.related_info}</p>
          <p className="desk-mutednote">{words.related_formula}</p>
          <div className="desk-tablewrap">
            <table className="desk-table hx-table">
              <colgroup>
                {labels.related_columns.map((column) => (
                  <col key={column.key} style={{ width: (readableWidths[column.key] ?? column.width) + 'px' }} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  {labels.related_columns.map((column) => (
                    <th key={column.key}>{column.key === 'product' ? 'รหัสสินค้า / Part No.' : column.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {related.rows.map((row) => (
                  <tr key={row.ref}>
                    {labels.related_columns.map((column) => (
                      <td key={column.key}>
                    {column.key.startsWith('roll_') && row.sale_unit !== 'ม้วน / roll'
                      ? 'ไม่ใช้กับรายการนี้'
                      : displayCell(column.key, row[column.key]) || 'ยังไม่ระบุ'}
                    {column.key === 'size' && row._input_details && (
                      <details className="hx-input-details" onClick={e => e.stopPropagation()} onDoubleClick={e => e.stopPropagation()}>
                        <summary>ดูข้อมูลจากหน้าเสนอราคาทั้งหมด</summary>
                        <div>{row._input_details}</div>
                      </details>
                    )}
                  </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="hx-close">
            <button type="button" onClick={() => setRelated(null)}>
              {labels.formulas.close}
            </button>
          </div>
        </dialog>
      )}
    </section>
  )
}
