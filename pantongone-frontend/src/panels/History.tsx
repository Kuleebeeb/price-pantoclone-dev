import { useEffect, useRef, useState } from 'react'
import {
  deleteQuotation,
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
import { HistoryTree } from './HistoryTree'
import './History.css'

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
}

function openSheet(html: string) {
  const w = window.open('', '_blank')
  if (!w) { window.alert('กรุณาอนุญาตป๊อปอัปเพื่อเปิดรายงานพิมพ์'); return }
  w.document.open()
  w.document.write(html)
  w.document.close()
}

type Row = { ref: string; [key: string]: string }

function printRows(rows: Row[]) {
  const escape = (value: string) => value.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!))
  const groups = new Map<string, Row[]>()
  // Group identical company names, not placeholder customer codes. Do not merge aliases.
  rows.forEach(r => { const key = (r.customer ?? '').trim() || `ไม่ระบุบริษัท (${r.customer_code})`; groups.set(key, [...(groups.get(key) ?? []), r]) })
  const cols: [string, string][] = [['ref','เลขอ้างอิง'],['date','วันที่'],['product','รหัสสินค้า'],['item','รายการ'],['size','ขนาด'],['thickness','ความหนา'],['grams','น้ำหนักต่อใบ (กรัม)'],['sale_unit','หน่วยขาย'],['calc_price','คำนวณ บาท/ใบ'],['price','บันทึกเดิม บาท/ใบ'],['price_kg','ฐานราคา บาท/กก.']]
  const sheets = [...groups].map(([company, entries]) => `<section><h1>PANTONG THAI PACK CO., LTD.</h1><h2>ประวัติราคาที่บันทึก — ${escape(company)}</h2><p>${entries.length} รายการ · รวมฉบับแก้ไข · ไม่ใช่ใบเสนอราคาฉบับอนุมัติ</p><table><thead><tr>${cols.map(([,label])=>`<th>${label}</th>`).join('')}</tr></thead><tbody>${entries.map(r=>`<tr>${cols.map(([key])=>`<td>${escape(displayCell(key,r[key]))}${key==='ref' ? `<br><small>รหัสลูกค้าเดิม: ${escape(r.customer_code || 'ไม่ระบุ')}</small>` : ''}</td>`).join('')}</tr>`).join('')}</tbody></table><p>รวมตามชื่อบริษัท รหัสลูกค้าเดิมแสดงใต้เลขอ้างอิง โดยไม่เปลี่ยนข้อมูลที่บันทึก</p><p>คำนวณ บาท/ใบ = ฐานราคา/กก. ÷ จำนวนใบ/กก. จากน้ำหนักของแต่ละรายการ ใช้ค่าหักจำนวนที่บันทึกเฉพาะหน่วยขายเป็นใบ; ขายเป็น กก. ไม่หักจำนวน</p><p>บันทึกเดิม บาท/ใบ แสดงราคาเดิมเพื่อเปรียบเทียบ ไม่ได้เขียนทับข้อมูล ช่องว่างหมายถึงไม่มีข้อมูลเพียงพอ ราคาฐานต่อ กก. ไม่ใช่ต้นทุนวัตถุดิบ</p></section>`).join('')
  const toolbar = `<nav class="report-tools"><button type="button" onclick="if(window.opener &amp;&amp; !window.opener.closed){window.opener.focus();window.close()}else{alert('กรุณาสลับกลับแท็บ PantongOne เดิม หน้านี้เป็นรายงานแยกต่างหาก')}">← กลับหน้าประวัติ</button><button type="button" onclick="window.print()">พิมพ์ / บันทึก PDF</button><span>กลับไปหน้าประวัติเดิม โดยไม่โหลดข้อมูลใหม่</span></nav>`
  openSheet(`<!doctype html><html lang="th"><meta charset="utf-8"><title>ประวัติราคาแยกบริษัท</title><style>@page{size:A4 landscape;margin:10mm}body{font:12px Tahoma,Arial,sans-serif;color:#000}h1{font-size:17px}h2{font-size:15px}.report-tools{position:sticky;top:0;background:#eef4fc;padding:12px;display:flex;gap:12px;align-items:center;border:1px solid #789}.report-tools button{font:16px Tahoma,sans-serif;padding:10px 18px;cursor:pointer}table{width:100%;border-collapse:collapse;table-layout:fixed}th,td{border:1px solid #444;padding:5px;overflow-wrap:anywhere}thead{display:table-header-group}tr{break-inside:avoid}section{break-after:page}section:last-child{break-after:auto}@media print{.report-tools,button{display:none}}</style>${toolbar}${sheets}</html>`)
}

const twoDecimalColumns = new Set(['grams', 'calc_price', 'price_kg', 'price', 'price_piece', 'pack', 'pack_kg'])

function displayCell(key: string, value: string | undefined) {
  const text = value ?? ''
  if (!twoDecimalColumns.has(key)) return text
  const plain = text.replace(/,/g, '').trim()
  if (!/^-?\d+(?:\.\d+)?$/.test(plain)) return text
  return Number(plain).toFixed(2)
}

export function History({ labels, products, customers, onEdit, onCopy, onCreateSample, onCreateDrawing, onStatus, bridgeOn = false }: Props) {
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
    if (!window.confirm(words.delete_confirm.split('{ref}').join(row.ref))) return
    try {
      await deleteQuotation(row.ref)
      onStatus(words.deleted_status.split('{ref}').join(row.ref))
      window.alert(words.deleted_body.split('{ref}').join(row.ref))
      search()
    } catch {
      window.alert(words.delete_missing)
    }
  }

  async function showRelated() {
    const row = needSelection()
    if (!row) return
    try {
      const answer = await relatedTable({
        product_reference: row._product_reference ?? '',
        item_description: row._item_description ?? '',
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
              <col key={column.key} style={{ width: column.width + 'px' }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              <th className="hx-pick">{bridge.check_col}</th>
              {labels.history_columns.map((column) => (
                <th key={column.key}>{column.label}</th>
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
                  <td key={column.key}>{displayCell(column.key, row[column.key])}</td>
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
        <button
          type="button"
          className="hx-sample"
          disabled={!selectedRow || !onCreateSample}
          onClick={() => selectedRow && onCreateSample?.(selectedRow.ref)}
        >
          ทำใบตัวอย่าง / Create Sample
        </button>
        <button
          type="button"
          className="hx-drawing"
          disabled={!selectedRow || !onCreateDrawing}
          onClick={() => selectedRow && onCreateDrawing?.(selectedRow.ref)}
        >
          ทำแบบอนุมัติ / Create Drawing
        </button>
        <button type="button" disabled={!selectedRow} onClick={() => selectedRow && onEdit(selectedRow.ref)}>
          แก้ไขข้อมูล / Edit
        </button>
        <button type="button" disabled={!selectedRow || !onCopy} onClick={() => selectedRow && onCopy?.(selectedRow.ref)}>คัดลอกเป็นรายการใหม่ / Copy as New</button>
        <button type="button" disabled={!selectedRow} onClick={printSelected}>
          {words.buttons.print_selected}
        </button>
        <button type="button" disabled={!selectedRow} onClick={deleteSelected}>
          {words.buttons.delete_selected}
        </button>
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

      <p className="desk-mutednote">{words.edit_note}</p>

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
                  <col key={column.key} style={{ width: column.width + 'px' }} />
                ))}
              </colgroup>
              <thead>
                <tr>
                  {labels.related_columns.map((column) => (
                    <th key={column.key}>{column.label}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {related.rows.map((row) => (
                  <tr key={row.ref}>
                    {labels.related_columns.map((column) => (
                      <td key={column.key}>{displayCell(column.key, row[column.key])}</td>
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
