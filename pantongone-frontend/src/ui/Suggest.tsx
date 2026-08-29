import { useEffect, useId, useMemo, useRef, useState } from 'react'
import './Suggest.css'

/* A BOX THAT REMEMBERS WHO HAS BEEN QUOTED BEFORE.
 *
 * There are 627 customers in the book and 17,391 quotations behind them.
 * Typing "Takane Electronics (Thailand) Co.,Ltd." by hand every time is not
 * merely slow: it is how one company ends up in the history four times under
 * four spellings, and how a search for their work quietly returns half of it.
 *
 * IT SUGGESTS, IT DOES NOT DECIDE. A new customer must still be typeable.
 * Nothing here rejects what is typed, corrects it, or fills the box on its own.
 *
 * THE CODE COMES WITH THE NAME, BUT ONLY WHEN THERE IS ONE. None of the rows
 * read out of the paper books carries a customer code, so most suggestions
 * bring a blank - and writing that blank over a code somebody has already typed
 * is the one way a suggestion box can do real harm.
 *
 * A <datalist> WOULD NOT DO. It cannot carry the code beside the name, it
 * cannot be ordered by how often a customer appears (browsers sort or truncate
 * it as they please), and on a touch screen it behaves differently in every
 * browser. This is fifty lines and behaves the same everywhere.
 *
 * A TAP MUST OPEN THE LIST TOO. ArrowDown-to-browse serves the keyboard, but
 * the people this box serves most work a touch screen on the factory floor
 * (the same P9 reasoning that bans tooltips): a phone has no ArrowDown. So a
 * click on the box, or on the ▾ beside it, opens the most-quoted list with
 * nothing typed - starting a quote is then two taps, not a company name.
 */

export type Suggestion = { customer: string; customer_code: string; times: number }

const MAX = 12

type Props = {
  label: string
  value: string
  onChange: (value: string) => void
  /** Called with the code that travels with the name - never with a blank. */
  onPick?: (code: string) => void
  rows: Suggestion[]
  disabled?: boolean
}

/** Which of the known customers match what has been typed. Pure, so it is
 *  testable without a browser.
 *
 *  Rows arrive ordered by how often the customer appears. Within that, a name
 *  that STARTS with what was typed comes first: typing "hon" wants Honda before
 *  "Nippon Honda Parts". */
export function matches(rows: Suggestion[], typed: string, limit = MAX): Suggestion[] {
  const needle = typed.trim().toLowerCase()
  if (!needle) return rows.slice(0, limit)
  const starts: Suggestion[] = []
  const contains: Suggestion[] = []
  for (const row of rows) {
    const name = row.customer.toLowerCase()
    if (name.startsWith(needle)) starts.push(row)
    else if (name.includes(needle) || row.customer_code.toLowerCase().includes(needle))
      contains.push(row)
    if (starts.length >= limit) break
  }
  return [...starts, ...contains].slice(0, limit)
}

export function Suggest({ label, value, onChange, onPick, rows, disabled }: Props) {
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const box = useRef<HTMLDivElement>(null)
  const listId = useId()

  const found = useMemo(() => (open ? matches(rows, value) : []), [open, rows, value])

  /* Closed by a click anywhere else, because a list floating over the next
   * field is worse than no list at all. The desktop program had exactly this
   * fault: its suggestion window outlived the box it belonged to and sat on top
   * of another tab with no way to dismiss it. */
  useEffect(() => {
    if (!open) return
    const away = (e: MouseEvent) => {
      if (!box.current?.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', away)
    return () => document.removeEventListener('mousedown', away)
  }, [open])

  function take(row: Suggestion) {
    onChange(row.customer)
    // Only when there IS one. A blank written back would erase a code somebody
    // has already typed.
    if (row.customer_code) onPick?.(row.customer_code)
    setOpen(false)
  }

  function onKey(e: React.KeyboardEvent) {
    if (e.key === 'ArrowDown') {
      // Down on a closed box opens it, including an empty one - that is how
      // somebody browses rather than searches.
      if (!open) {
        setOpen(true)
        setHighlight(0)
      } else setHighlight((h) => Math.min(h + 1, found.length - 1))
      e.preventDefault()
      return
    }
    if (!open) return
    if (e.key === 'ArrowUp') {
      setHighlight((h) => Math.max(h - 1, 0))
      e.preventDefault()
    } else if (e.key === 'Enter' && found[highlight]) {
      take(found[highlight])
      e.preventDefault()
    } else if (e.key === 'Escape') {
      // Closes and KEEPS what was typed. Escape must never undo typing.
      setOpen(false)
      e.preventDefault()
    }
  }

  return (
    <div className="sug" ref={box}>
      <input
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? listId : undefined}
        aria-autocomplete="list"
        role="combobox"
        value={value}
        disabled={disabled}
        onChange={(e) => {
          onChange(e.target.value)
          setOpen(true)
          setHighlight(0)
        }}
        onClick={() => {
          if (disabled) return
          setOpen(true)
          setHighlight(0)
        }}
        onKeyDown={onKey}
      />
      <button
        type="button"
        className="sug-toggle"
        // Not in the tab order: the keyboard already has ArrowDown, and one
        // more tab stop per field slows the form it exists to speed up.
        tabIndex={-1}
        aria-label={label}
        aria-expanded={open}
        disabled={disabled}
        // mousedown for the same reason as the options below: a click would
        // blur the input and close the list before the toggle ever fired.
        onMouseDown={(e) => {
          e.preventDefault()
          setOpen((was) => !was)
          setHighlight(0)
        }}
      >
        ▾
      </button>
      {open && found.length > 0 && (
        <ul className="sug-list" id={listId} role="listbox">
          {found.map((row, index) => (
            <li key={row.customer}>
              <button
                type="button"
                role="option"
                aria-selected={index === highlight}
                className={index === highlight ? 'is-on' : ''}
                // mousedown, not click: the input's blur would close the list
                // out from under the pointer before a click ever landed.
                onMouseDown={(e) => {
                  e.preventDefault()
                  take(row)
                }}
              >
                <span>{row.customer}</span>
                {row.customer_code && <em>{row.customer_code}</em>}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
