import { useEffect, useState } from 'react'
import {
  historyTreeCustomers,
  historyTreeProducts,
  historyTreeRows,
  type Labels,
  type SearchParams,
  type TreeCustomer,
  type TreeProduct,
} from '@/lib/api'

/* THE BOOK AS FOLDERS.
 *
 * Customer > product (same name + same size, folded into one) > every quote
 * of that product, newest first. Asked for with a screenshot on 28-08-2026:
 * "like the folder tree on a computer - group by customer first, click to
 * see the customer's old prices".
 *
 * Each level is fetched when its folder opens, never before: the book holds
 * 28,000 rows and a tree that loads them all up front is the flat table with
 * extra steps. Every word and every figure comes from the server; this file
 * only nests them.
 */

type Props = {
  labels: Labels
  filters: SearchParams
  /** The same Details window the flat table opens on a double-click. */
  onOpen: (quoteRef: string) => void
  onCount: (text: string) => void
  /** The rows ticked for PacOs, shared with the flat table so a tick
   *  survives switching views. Absent = no tick boxes. */
  picked?: Set<string>
  onPick?: (quoteRef: string) => void
}

type Row = { ref: string; [key: string]: string }

const folderKey = (p: TreeProduct) => p.product_name + ' ' + p.size

export function HistoryTree({ labels, filters, onOpen, onCount, picked, onPick }: Props) {
  const words = labels.history
  const [customers, setCustomers] = useState<TreeCustomer[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [openCustomer, setOpenCustomer] = useState('')
  const [products, setProducts] = useState<TreeProduct[]>([])
  const [openProduct, setOpenProduct] = useState('')
  const [rows, setRows] = useState<Row[] | null>(null)

  /* The filters above the tree apply to every level, so a new filter set
   * closes what was open: a folder opened under other filters would show
   * rows the filters were meant to hide. */
  useEffect(() => {
    const ac = new AbortController()
    setLoading(true)
    setOpenCustomer('')
    setOpenProduct('')
    setRows(null)
    historyTreeCustomers(filters, ac.signal)
      .then((answer) => {
        if (ac.signal.aborted) return
        setCustomers(answer.groups)
        onCount(answer.count_text)
        setError('')
      })
      .catch((e: Error) => {
        if (ac.signal.aborted || e.name === 'AbortError') return
        setError(e.message)
      })
      .finally(() => {
        if (!ac.signal.aborted) setLoading(false)
      })
    return () => ac.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters])

  async function toggleCustomer(name: string) {
    if (openCustomer === name) {
      setOpenCustomer('')
      setOpenProduct('')
      setRows(null)
      return
    }
    setOpenCustomer(name)
    setOpenProduct('')
    setRows(null)
    setProducts([])
    try {
      const answer = await historyTreeProducts(name, filters)
      setProducts(answer.groups)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  async function toggleProduct(p: TreeProduct) {
    const key = folderKey(p)
    if (openProduct === key) {
      setOpenProduct('')
      setRows(null)
      return
    }
    setOpenProduct(key)
    setRows(null)
    try {
      const answer = await historyTreeRows(openCustomer, p.product_name, p.size, filters)
      setRows(answer.rows as Row[])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const cols = labels.history_columns
  const ticks = onPick !== undefined

  function leaves() {
    return (
      <div className="desk-tablewrap">
        <table className="desk-table hx-table">
          <colgroup>
            {ticks && <col style={{ width: '44px' }} />}
            {cols.map((column) => (
              <col key={column.key} style={{ width: column.width + 'px' }} />
            ))}
          </colgroup>
          <thead>
            <tr>
              {ticks && <th className="hx-pick">{labels.bridge.check_col}</th>}
              {cols.map((column) => (
                <th key={column.key}>{column.label}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows === null && (
              <tr>
                <td colSpan={cols.length + (ticks ? 1 : 0)} className="hx-empty">
                  {words.tree_loading}
                </td>
              </tr>
            )}
            {rows?.map((row) => (
              <tr key={row.ref} onDoubleClick={() => onOpen(row.ref)}>
                {ticks && (
                  <td className="hx-pick" onDoubleClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      aria-label={`${labels.bridge.check_col} ${row.ref}`}
                      checked={picked?.has(row.ref) ?? false}
                      onChange={() => onPick?.(row.ref)}
                    />
                  </td>
                )}
                {cols.map((column) => (
                  <td key={column.key}>{row[column.key] ?? ''}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    )
  }

  function productRows() {
    return (
      <table>
        <thead>
          <tr>
            <th>{words.tree_col_product}</th>
            <th>{words.tree_col_size}</th>
            <th>{words.tree_col_unit}</th>
            <th className="num">{words.tree_col_quotes}</th>
            <th>{words.tree_col_period}</th>
            <th className="num">{words.tree_col_latest}</th>
            <th className="num">{words.tree_col_range}</th>
          </tr>
        </thead>
        <tbody>
          {products.length === 0 && (
            <tr>
              <td colSpan={7} className="hx-empty">
                {words.tree_loading}
              </td>
            </tr>
          )}
          {products.flatMap((p) => {
            const key = folderKey(p)
            const pOpen = key === openProduct
            const out = [
              <tr
                key={'g:' + key}
                className={'folder level-1' + (pOpen ? ' is-open' : '')}
                role="treeitem"
                aria-expanded={pOpen}
                onClick={() => toggleProduct(p)}
              >
                <td>
                  <span className="caret">{pOpen ? '▾' : '▸'}</span>
                  {p.product_name}
                </td>
                <td>{p.size}</td>
                <td>{p.sale_unit}</td>
                <td className="num">{p.quotes}</td>
                <td>{p.period}</td>
                <td className="num">{p.latest_price}</td>
                <td className="num">{p.price_range}</td>
              </tr>,
            ]
            if (pOpen) {
              out.push(
                <tr key={'r:' + key} className="leaves">
                  <td colSpan={7}>{leaves()}</td>
                </tr>,
              )
            }
            return out
          })}
        </tbody>
      </table>
    )
  }

  return (
    <div className="hx-tree" role="tree" aria-label={words.view_tree}>
      {error && <p className="desk-status">{error}</p>}
      <table>
        <thead>
          <tr>
            <th>{words.tree_col_customer}</th>
            <th>{words.tree_col_code}</th>
            <th className="num">{words.tree_col_products}</th>
            <th className="num">{words.tree_col_quotes}</th>
            <th>{words.tree_col_period}</th>
          </tr>
        </thead>
        <tbody>
          {loading && (
            <tr>
              <td colSpan={5} className="hx-empty">
                {words.tree_loading}
              </td>
            </tr>
          )}
          {!loading && customers.length === 0 && (
            <tr>
              <td colSpan={5} className="hx-empty">
                {words.tree_empty}
              </td>
            </tr>
          )}
          {customers.flatMap((c) => {
            const isOpen = c.customer === openCustomer
            const out = [
              <tr
                key={'c:' + c.customer}
                className={'folder' + (isOpen ? ' is-open' : '')}
                role="treeitem"
                aria-expanded={isOpen}
                onClick={() => toggleCustomer(c.customer)}
              >
                <td>
                  <span className="caret">{isOpen ? '▾' : '▸'}</span>
                  {c.customer}
                </td>
                <td>{c.customer_code}</td>
                <td className="num">{c.products}</td>
                <td className="num">{c.quotes}</td>
                <td>{c.period}</td>
              </tr>,
            ]
            if (isOpen) {
              out.push(
                <tr key={'p:' + c.customer} className="leaves">
                  <td colSpan={5}>{productRows()}</td>
                </tr>,
              )
            }
            return out
          })}
        </tbody>
      </table>
    </div>
  )
}
