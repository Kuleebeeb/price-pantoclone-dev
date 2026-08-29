import { useEffect, useRef } from 'react'
import type { Meta } from '@/lib/api'
import './Formulas.css'

/* THE FORMULA VARIABLES WINDOW - app.py show_formula_help (3795-3811).
 *
 * The toolbar's ตัวแปรสูตร button opens a REFERENCE, not an editor: the list
 * of variables a formula may use, in a monospace face, with the operators
 * sentence under it. The editing itself happens where the desktop puts it -
 * the weight-formula box on the Production Data panel - and the arithmetic
 * happens on the server, by the same formula_engine.py the .exe uses. A
 * browser that evaluated a formula would be a second arithmetic (LAW P1) and,
 * with eval, a way to run anything at all.
 */

type Props = {
  meta: Meta
  onClose: () => void
}

export function Formulas({ meta, onClose }: Props) {
  const dialog = useRef<HTMLDialogElement>(null)
  const words = meta.labels.formulas

  useEffect(() => {
    dialog.current?.showModal()
  }, [])

  /* A native <dialog>, so the focus trap, the backdrop and Escape are the
   * browser's rather than three more things to get right here. */
  return (
    <dialog className="fx" ref={dialog} onClose={onClose}>
      <h2>{words.title}</h2>

      {/* The desktop draws this in Consolas 10 (app.py:3808-3811), and the
          text arrives whole from the server - names, the two-space "=", the
          operators and the note, in its order. */}
      <pre className="fx-text">{meta.formula_help_text}</pre>

      <div className="fx-close">
        <button type="button" onClick={() => dialog.current?.close()}>
          {words.close}
        </button>
      </div>
    </dialog>
  )
}
