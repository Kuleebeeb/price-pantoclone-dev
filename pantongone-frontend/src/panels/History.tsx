import { useEffect, useRef, useState } from 'react'
import {
  deleteQuotation,
  historySearch,
  printSaved,
  pushToPacos,
  quotationDetails,
  relatedTable,
  type Customer,
  type Labels,
  type SearchParams,
} from '@/lib/api'
import { Suggest } from '@/ui/Suggest'
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
  onStatus: (text: string) => void
  /** From /api/meta: the server has a key for PacOs. Without it the button
   *  stays, disabled, saying why - a button that vanishes is a feature
   *  nobody knows exists. */
  bridgeOn?: boolean
}

function openSheet(html: string) {
  const w = window.open('', '_blank')
  if (!w) return
  w.document.open()
  w.document.write(html)
  w.document.close()
}

type Row = { ref: string; [key: string]: string }

export function History({ labels, products, customers, onEdit, onStatus, bridgeOn = false }: Props) {
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

  function search(over: Partial<Record<'customer' | 'productKey' | 'sort', string>> = {}) {
    inFlight.current?.abort()
    const ac = new AbortController()
    inFlight.current = ac
    const params: SearchParams = {
      customer: over.customer ?? customer,
      item,
      product_key: over.productKey ?? productKey,
      size,
      date_from: dateFrom,
      date_to: dateTo,
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
    search({ customer: '', productKey: '', sort: 'newest' })
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
      const sheet = await printSaved(row.ref)
      openSheet(sheet.html)
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
            onPick={() => search()}
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
            {Object.entries(products).map(([key, label]) => (
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
                  <td key={column.key}>{row[column.key]}</td>
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
        <button type="button" disabled={!selectedRow} onClick={() => selectedRow && onEdit(selectedRow.ref)}>
          {words.buttons.edit}
        </button>
        <button type="button" disabled={!selectedRow} onClick={printSelected}>
          {words.buttons.print_selected}
        </button>
        <button type="button" disabled={!selectedRow} onClick={deleteSelected}>
          {words.buttons.delete_selected}
        </button>
        <button type="button" onClick={showRelated}>
          {words.buttons.related}
        </button>
        {/* Drawn only while the bridge is on. It used to sit disabled with a
            tooltip when off; since 14-09-2026 (PacOs D45) the bridge is gone
            for good, and a dead button with an explanation is still a dead
            button on every history screen. */}
        {bridgeOn && (
          <button
            type="button"
            className="hx-pacos"
            disabled={sending || picked.size === 0}
            onClick={sendToPacos}
          >
            {picked.size > 0 ? bridge.button_count.split('{n}').join(String(picked.size)) : bridge.button}
          </button>
        )}
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
                      <td key={column.key}>{row[column.key]}</td>
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
