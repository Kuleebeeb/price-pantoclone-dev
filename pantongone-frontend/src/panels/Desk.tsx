import { useEffect, useMemo, useRef, useState } from 'react'
import {
  calculate,
  getCustomers,
  planningCompare,
  planningSource,
  planningSources,
  printHtml,
  quotationForm,
  saveQuotation,
  workOrderHtml,
  type Customer,
  type Labels,
  type Meta,
  type Session,
  type SourceRow,
} from '@/lib/api'
import type { CalcRequest, CalcResponse, Form, ProductKey } from '@/lib/calc'
import { History } from '@/panels/History'
import { Drawing } from '@/panels/Drawing'
import { Coa } from '@/panels/Coa'
import { SampleInspection } from '@/panels/SampleInspection'
import { Formulas } from '@/panels/Formulas'
import { Suggest } from '@/ui/Suggest'
import './Desk.css'

/* THE PROGRAM'S OWN WINDOW - app.py v1.7.1 "(Phase 1) - Planning screen".
 *
 * Every word on this screen comes from /api/meta - api/screen.py lifted them
 * out of app.py verbatim. This file holds NO Thai of its own, on purpose: the
 * desktop wording and the web wording cannot drift apart if there is only one
 * copy of it, and the copy lives beside the formulas it describes.
 *
 * WHAT THE DESKTOP ACTUALLY DRAWS, and this screen mirrors: the Pricing tab is
 * ONE compact card plus the action bar pinned under it - the tall
 * Customer & Quotation and Dimensions cards exist in app.py but are
 * grid_remove()d at build and the buttons that could reopen them sit inside
 * the removed cards, so no user has ever seen them. The Planning tab is the
 * source picker, the production panel and the shop-floor work orders.
 *
 * CALCULATION IS A BUTTON, NOT A KEYSTROKE. The desktop prints nothing until
 * คำนวณราคา is pressed - that is what step 2 of the step bar says - and a step
 * bar over a screen that behaves differently would be the screen contradicting
 * itself.
 */

type Tab = 'pricing' | 'sample' | 'planning' | 'drawing' | 'coa' | 'history'

/* Written down ONCE, and they are the desktop's own starting values
 * (app.py DEFAULTS, 67-73; roof/mesh at 1777-1796). */
const DEFAULTS = {
  density: '0.92',
  material_price: '65',
  deduction: '10',
  order_quantity: '1000',
  bottom_allowance: '1',
  roof_gsm: '120',
  mesh_gsm: '80',
}

export function blank(meta: Meta | null): Form {
  return {
    customer: '',
    customer_code: '',
    quote_date: new Date().toISOString().slice(0, 10),
    item_description: '',
    product_reference: '',
    product_key: 'flat',
    width: '',
    width_unit: 'ซม.',
    length: '',
    length_unit: 'ซม.',
    height: '',
    gusset: '',
    sold_length: '',
    sold_length_unit: 'เมตร',
    thickness: '',
    thickness_unit: 'มม.',
    thickness_mode: 'pair',
    bottom_allowance: DEFAULTS.bottom_allowance,
    /* The desktop's length-reference combobox lives on a card v1.7.1 never
     * draws, so the reference simply stays at its default. */
    length_reference: Object.values(meta?.length_references ?? {})[0] ?? '',
    density: DEFAULTS.density,
    material_price: DEFAULTS.material_price,
    deduction: DEFAULTS.deduction,
    apply_deduction: true,
    sale_basis: 'kg',
    price_per_kg: '',
    price_per_piece: '',
    order_quantity: DEFAULTS.order_quantity,
    pack_quantity: '',
    sack_quantity: '',
    control_min: '',
    control_max: '',
    roof_gsm: DEFAULTS.roof_gsm,
    mesh_gsm: DEFAULTS.mesh_gsm,
    weight_formula: '',
    price_formula: '',
    tolerance_width: '', tolerance_length: '', tolerance_thickness: '',
    tolerance_gusset_left: '', tolerance_gusset_right: '', special_requirements: '',
  }
}

/* A DRAFT, KEPT IN THIS BROWSER - the same promise the desktop's
 * latest_pricing_draft.json makes, no more. */
const DRAFT_KEY = 'pantongone.draft'

function keepDraft(form: Form) {
  try {
    localStorage.setItem(DRAFT_KEY, JSON.stringify(form))
  } catch {
    /* A private window, or storage full. Losing a draft must never be allowed
       to stop the thing being typed. */
  }
}

function heldDraft(): Form | null {
  try {
    const raw = localStorage.getItem(DRAFT_KEY)
    return raw ? (JSON.parse(raw) as Form) : null
  } catch {
    return null
  }
}

// An empty box is not a zero. It makes an incomplete request, and the server
// refuses it by name rather than pricing a bag with no width.
function n(raw: string): number {
  const v = Number(String(raw).replace(/,/g, '').trim())
  return Number.isFinite(v) ? v : 0
}

export function toRequest(form: Form, meta: Meta | null): CalcRequest {
  return {
    product_key: form.product_key,
    width: { value: n(form.width), unit: form.width_unit },
    length: { value: n(form.length), unit: form.length_unit },
    height: { value: n(form.height), unit: form.length_unit },
    gusset: { value: n(form.gusset), unit: form.width_unit },
    sold_length: { value: n(form.sold_length), unit: form.sold_length_unit || 'เมตร' },
    bottom_allowance: { value: n(form.bottom_allowance), unit: form.length_unit },
    thickness: {
      value: n(form.thickness),
      unit: form.thickness_unit,
      mode: form.thickness_mode,
    },
    length_reference: form.length_reference,
    density_g_cm3: n(form.density),
    material_price_per_kg: n(form.material_price),
    deduction_percent: n(form.deduction),
    apply_deduction: form.apply_deduction,
    sale_basis: form.sale_basis,
    selling_price_per_piece_override: n(form.price_per_piece),
    selling_price_per_kg_override: n(form.price_per_kg),
    pack_quantity: n(form.pack_quantity),
    sack_quantity: n(form.sack_quantity),
    order_quantity: n(form.order_quantity),
    control_min_g: n(form.control_min),
    control_max_g: n(form.control_max),
    roof_gsm: n(form.roof_gsm),
    mesh_gsm: n(form.mesh_gsm),
    /* Empty means "the default for THIS product", which lives on the server
     * beside the formulas themselves (LAW P1). */
    weight_formula: form.weight_formula,
    price_formula: form.price_formula || meta?.default_price_formula || '',
    tolerance_width: { value: n(form.tolerance_width), unit: 'มม.' },
    tolerance_length: { value: n(form.tolerance_length), unit: 'มม.' },
    tolerance_thickness: { value: n(form.tolerance_thickness), unit: 'มม.' },
    tolerance_gusset_left: { value: n(form.tolerance_gusset_left), unit: 'มม.' },
    tolerance_gusset_right: { value: n(form.tolerance_gusset_right), unit: 'มม.' },
    special_requirements: form.special_requirements,
  }
}

/* The live caption over the adjusted-items tile (app.py:589-609): it follows
 * the percentage as it is typed, and mid-typing values like "1." are shown as
 * typed rather than blinked at. */
export function deductionCaption(labels: Labels, form: Form): string {
  if (!form.apply_deduction) return labels.notes.deduction_caption_off
  const raw = form.deduction.trim() || DEFAULTS.deduction
  const num = Number(raw.replace(/,/g, ''))
  const shown = Number.isFinite(num) && raw !== '' ? String(num) : raw
  return labels.notes.deduction_caption.split('{n}').join(shown)
}

/* Markup% = ((basis/material) - 1) x 100, shown LIVE as the desktop shows it
 * (app.py:2784-2795). Display only - the figure that is saved is the one the
 * server derives again from the same inputs. */
export function liveMarkup(form: Form): string {
  const material = n(form.material_price)
  const basis = n(form.price_per_kg)
  if (material <= 0 || basis <= 0) return ''
  return (((basis / material) - 1) * 100).toFixed(2)
}

type PlanningState = {
  search: string
  ref: string
  summary: string
  width: string
  length: string
  thickness: string
  gusset: string
  packaging: string
  quantity: string
  notes: string
  compare: string
  productKey: string
  sackQuantity: string
  sackWeight: string
  gramsPerItem: string
  referenceGramsPerItem: string
  itemsPerKg: string
  adjustedItems: string
  toleranceWidth: string
  toleranceLength: string
  toleranceThickness: string
  toleranceGussetLeft: string
  toleranceGussetRight: string
  drawingDocNo: string
  specialFeatures: string
  salesProduct: string
  salesPartNo: string
  salesSize: string
  salesWidth: string
  salesLength: string
  salesThickness: string
  salesThicknessMode: string
  saleBasis: 'piece' | 'kg'
  packageStyle: 'ห่อ / Pack' | 'พับ / Fold'
  smallPackQuantity: string
  packageCountPerSack: string
  quotedSmallPackQuantity: string
  quotedPackageCountPerSack: string
  packagingChoice: 'quoted' | 'new'
  maximumSackWeight: string
}

const emptyPlanning: PlanningState = {
  search: '',
  ref: '',
  summary: '',
  width: '',
  length: '',
  thickness: '',
  gusset: '',
  packaging: '',
  quantity: '',
  notes: '',
  compare: '',
  productKey: '', sackQuantity: '', sackWeight: '', gramsPerItem: '', referenceGramsPerItem: '', itemsPerKg: '', adjustedItems: '',
  toleranceWidth: '', toleranceLength: '', toleranceThickness: '', toleranceGussetLeft: '', toleranceGussetRight: '',
  drawingDocNo: '', specialFeatures: '',
  salesProduct: '', salesPartNo: '', salesSize: '', salesWidth: '', salesLength: '', salesThickness: '', salesThicknessMode: '',
  saleBasis: 'piece', packageStyle: 'ห่อ / Pack', smallPackQuantity: '', packageCountPerSack: '',
  quotedSmallPackQuantity: '', quotedPackageCountPerSack: '', packagingChoice: 'quoted',
  maximumSackWeight: '',
}

function openSheet(html: string) {
  const w = window.open('', '_blank')
  if (!w) return
  w.document.open()
  w.document.write(html)
  w.document.close()
}

type Props = {
  meta: Meta | null
  session: Session
  onSignOut: () => void
}

export function Desk({ meta, session, onSignOut }: Props) {
  const [form, setForm] = useState<Form>(() => blank(meta))
  const [tab, setTab] = useState<Tab>('pricing')
  const [answer, setAnswer] = useState<CalcResponse | null>(null)
  const [status, setStatus] = useState<string | null>(null)
  const [saved, setSaved] = useState('')
  const [refText, setRefText] = useState<string | null>(null)
  const [saving, setSaving] = useState(false)
  const [customers, setCustomers] = useState<Customer[]>([])
  const [helpOpen, setHelpOpen] = useState(false)
  const [planning, setPlanning] = useState<PlanningState>(emptyPlanning)
  const [workDept, setWorkDept] = useState<'blown' | 'cutting'>('blown')
  /* Set when the form was loaded from a saved record: the save becomes a
   * linked revision, never an overwrite (app.py editing_source_ref). */
  const [editingRef, setEditingRef] = useState('')
  const inFlight = useRef<AbortController | null>(null)

  /* Read once and kept. 627 names is nothing to filter in memory and everything
   * to re-query seventeen thousand rows for while somebody is typing. */
  useEffect(() => {
    getCustomers()
      .then((answer) => setCustomers(answer.rows))
      .catch(() => setCustomers([]))
  }, [])

  /* The draft follows the typing. AN EMPTY FORM IS NOT A DRAFT. */
  useEffect(() => {
    const worthKeeping = Boolean(form.customer.trim() || form.width.trim() || form.length.trim())
    if (!worthKeeping) return
    const t = window.setTimeout(() => keepDraft(form), 800)
    return () => window.clearTimeout(t)
  }, [form])

  /* The length-reference default cannot be filled until meta has arrived.
   * It fills THAT ONE FIELD. */
  useEffect(() => {
    const first = Object.values(meta?.length_references ?? {})[0]
    if (!first) return
    setForm((f) => (f.length_reference ? f : { ...f, length_reference: first }))
  }, [meta])

  const labels = meta?.labels
  const drawn: string[] = useMemo(
    () => labels?.fields_by_product?.[form.product_key] ?? ['width', 'length', 'thickness'],
    [labels, form.product_key],
  )
  const isBag = labels?.asks_length_reference?.includes(form.product_key) ?? false

  const set = (patch: Partial<Form>) => {
    setForm((f) => ({ ...f, ...patch }))
  }

  /* CALCULATE, THE BUTTON. The previous request is abandoned rather than
   * raced: two answers arriving out of order would leave the older press's
   * figures on screen. */
  async function runCalculate(quiet = false): Promise<CalcResponse | null> {
    if (!labels) return null
    inFlight.current?.abort()
    const ac = new AbortController()
    inFlight.current = ac
    try {
      const r = await calculate(toRequest(form, meta), ac.signal)
      if (ac.signal.aborted) return null
      setAnswer(r)
      setStatus(labels.notes.calculated_ok)
      return r
    } catch (e) {
      if (ac.signal.aborted || (e instanceof Error && e.name === 'AbortError')) return null
      const message = e instanceof Error ? e.message : String(e)
      setAnswer(null)
      setStatus(labels.notes.check_input + message)
      if (!quiet) window.alert(message)
      return null
    }
  }

  /* The desktop's three header refusals, before anything is sent
   * (app.py:3236-3244). */
  function validateHeader(): boolean {
    if (!labels) return false
    if (!form.customer.trim()) {
      window.alert(labels.notes.need_customer)
      return false
    }
    if (!form.customer_code.trim()) {
      window.alert(labels.notes.need_customer_code)
      return false
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.quote_date)) {
      window.alert(labels.notes.bad_date)
      return false
    }
    return true
  }

  async function keep() {
    if (saving || !labels) return
    if (!validateHeader()) return
    const calculated = await runCalculate()
    if (!calculated) return
    setSaving(true)
    try {
      /* The QUESTION goes up, never the answer: the server works the figures
       * out again and stores what IT got (LAW K1). */
      const row = await saveQuotation({
        calc: toRequest(form, meta),
        quote_date: form.quote_date,
        customer: form.customer,
        customer_code: form.customer_code,
        item_description: form.item_description,
        product_reference: form.product_reference,
        revised_from_ref: editingRef,
      })
      setSaved(row.quote_ref)
      setRefText(labels.notes.quote_ref_prefix + row.quote_ref)
      setStatus(labels.notes.saved_status_prefix + row.quote_ref)
      window.alert(
        labels.notes.saved_body
          + '\n' + labels.notes.quote_ref_prefix + row.quote_ref
          + (editingRef ? '\n' + labels.history.revised_from.split('{ref}').join(editingRef) : ''),
      )
      setEditingRef('')
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setStatus(labels.notes.check_input + message)
      window.alert(message)
    } finally {
      setSaving(false)
    }
  }

  /* Print Summary: the draft is saved FIRST, then the sheet is asked for -
   * the desktop's own order (app.py:3538-3565). */
  async function printSummary() {
    if (!labels) return
    keepDraft(form)
    if (!validateHeader()) return
    try {
      const sheet = await printHtml({
        calc: toRequest(form, meta),
        quote_date: form.quote_date,
        customer: form.customer,
        customer_code: form.customer_code,
        item_description: form.item_description,
        product_reference: form.product_reference,
        quote_ref: saved,
        revised_from_ref: editingRef,
      })
      openSheet(sheet.html)
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      window.alert(message)
      setStatus(labels.notes.print_draft_saved)
    }
  }

  /* Restore Latest Draft - always offered, and it ASKS first, both exactly as
   * the desktop does (app.py:3600-3667). */
  function restoreDraft() {
    if (!labels) return
    const draft = heldDraft()
    if (!draft) {
      window.alert(labels.notes.draft_none_body)
      return
    }
    if (!window.confirm(labels.notes.draft_confirm_body)) return
    setForm({ ...blank(meta), ...draft })
    setAnswer(null)
    setSaved('')
    setRefText(labels.notes.draft_ref)
    setStatus(labels.notes.draft_restored)
    setTab('pricing')
  }

  function newRecord() {
    setForm(blank(meta))
    setAnswer(null)
    setSaved('')
    setRefText(null)
    setEditingRef('')
    setStatus(labels ? labels.history.new_status : null)
    setTab('pricing')
  }

  /* The history tab's Edit button: the saved record poured back into the
   * form, box-ready, then straight to the pricing tab and a recalculation -
   * the desktop's own sequence (app.py:4185-4296). */
  async function editFromHistory(quoteRef: string) {
    if (!labels) return
    try {
      const answer = await quotationForm(quoteRef)
      setForm({ ...blank(meta), ...(answer.form as Partial<Form>) })
      setEditingRef(answer.quote_ref)
      setSaved('')
      setRefText(answer.ref_text)
      setStatus(answer.status)
      setAnswer(null)
      setTab('pricing')
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  // ------------------------------------------------------------ planning tab

  async function loadPlanningSource() {
    if (!labels) return
    const selected = planning.search.trim()
    if (!selected) {
      window.alert(labels.planning.messages.select_first)
      return
    }
    try {
      const src = await planningSource(selected)
      setPlanning((p) => ({
        ...p,
        search: src.line,
        ref: src.quote_ref,
        summary: src.summary,
        width: src.width,
        length: src.length,
        thickness: src.thickness,
        gusset: src.gusset,
        packaging: src.package,
        quantity: src.quantity,
        productKey: src.product_key,
        sackQuantity: src.sack_quantity,
        sackWeight: src.sack_weight_kg,
        gramsPerItem: src.grams_per_item,
        referenceGramsPerItem: src.grams_per_item,
        itemsPerKg: src.items_per_kg,
        adjustedItems: src.adjusted_items,
        toleranceWidth: src.tolerance_width_mm,
        toleranceLength: src.tolerance_length_mm,
        toleranceThickness: src.tolerance_thickness_mm,
        toleranceGussetLeft: src.tolerance_gusset_left_mm,
        toleranceGussetRight: src.tolerance_gusset_right_mm,
        drawingDocNo: src.drawing_doc_no,
        specialFeatures: src.special_features,
        salesProduct: src.sales_product,
        salesPartNo: src.sales_part_no,
        salesSize: src.sales_size,
        salesWidth: src.sales_width,
        salesLength: src.sales_length,
        salesThickness: src.sales_thickness,
        salesThicknessMode: src.sales_thickness_mode,
        saleBasis: src.sale_basis,
        smallPackQuantity: src.small_pack_quantity,
        packageCountPerSack: src.package_count_per_sack,
        quotedSmallPackQuantity: src.small_pack_quantity,
        quotedPackageCountPerSack: src.package_count_per_sack,
        packagingChoice: 'quoted',
        maximumSackWeight: '',
        compare: '',
      }))
      setStatus(src.status)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  async function compareWeight() {
    if (!labels) return
    if (!planning.ref) {
      window.alert(labels.planning.messages.missing_source)
      return
    }
    try {
      const out = await planningCompare({
        quote_ref: planning.ref,
        quantity: planning.quantity,
        width: planning.width,
        length: planning.length,
        thickness: planning.thickness,
        gusset: planning.gusset,
        sack_quantity: planning.sackQuantity,
      })
      setPlanning((p) => ({ ...p, compare: out.line, gramsPerItem: out.grams_per_item,
        itemsPerKg: out.items_per_kg, adjustedItems: out.adjusted_items, sackWeight: out.sack_weight_kg }))
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  function copyWorkOrder(dept: 'blown' | 'cutting'): boolean {
    if (!labels) return false
    if (!planning.search.trim()) {
      window.alert(labels.planning.messages.missing_source_work_order)
      return false
    }
    setStatus(
      labels.planning.messages.prepared.split('{dept}').join(labels.work_orders.names[dept]),
    )
    return true
  }

  async function printWorkOrder(dept: 'blown' | 'cutting') {
    if (!labels) return
    if (!copyWorkOrder(dept)) return
    try {
      const sheet = await workOrderHtml({
        department: dept,
        source: planning.summary,
        width: planning.width,
        length: planning.length,
        thickness: planning.thickness,
        gusset: planning.gusset,
        package: planning.packaging,
        notes: planning.notes,
        drawing_doc_no: planning.drawingDocNo,
        special_features: planning.specialFeatures,
        sack_quantity: planning.sackQuantity,
        sack_weight: planning.sackWeight,
        tolerance_width: planning.toleranceWidth,
        tolerance_length: planning.toleranceLength,
        tolerance_thickness: planning.toleranceThickness,
        tolerance_gusset_left: planning.toleranceGussetLeft,
        tolerance_gusset_right: planning.toleranceGussetRight,
        grams_per_item: planning.gramsPerItem,
        items_per_kg: planning.itemsPerKg,
        adjusted_items: planning.adjustedItems,
        sale_basis: planning.saleBasis,
        package_style: planning.packageStyle,
        small_pack_quantity: planning.smallPackQuantity,
        package_count_per_sack: planning.packageCountPerSack,
        total_package_quantity: planning.saleBasis === 'piece' && Number(planning.smallPackQuantity) > 0 && Number(planning.packageCountPerSack) > 0 ? String(Number(planning.smallPackQuantity) * Number(planning.packageCountPerSack)) : '',
        small_pack_weight: planning.saleBasis === 'piece' && Number(planning.smallPackQuantity) > 0 && Number(planning.gramsPerItem) > 0 ? (Number(planning.smallPackQuantity) * Number(planning.gramsPerItem) / 1000).toFixed(4) : planning.smallPackQuantity,
        width_limits: Number(planning.width) > 0 ? `${(Number(planning.width) * 10 - Number(planning.toleranceWidth)).toFixed(1)} - ${(Number(planning.width) * 10 + Number(planning.toleranceWidth)).toFixed(1)} mm` : '',
        length_limits: Number(planning.length) > 0 ? `${(Number(planning.length) * 10 - Number(planning.toleranceLength)).toFixed(1)} - ${(Number(planning.length) * 10 + Number(planning.toleranceLength)).toFixed(1)} mm` : '',
        thickness_limits: Number(planning.thickness) > 0 ? `${(Number(planning.thickness) - Number(planning.toleranceThickness)).toFixed(3)} - ${(Number(planning.thickness) + Number(planning.toleranceThickness)).toFixed(3)} mm` : '',
        gusset_limits: Number(planning.gusset) > 0 ? `${(Number(planning.gusset) * 10 - Math.max(Number(planning.toleranceGussetLeft), Number(planning.toleranceGussetRight))).toFixed(1)} - ${(Number(planning.gusset) * 10 + Math.max(Number(planning.toleranceGussetLeft), Number(planning.toleranceGussetRight))).toFixed(1)} mm` : '',
        standard_sack_weight: planning.sackWeight,
        maximum_sack_weight: planning.saleBasis === 'piece' && acceptedWeightMax > 0 && Number(planning.sackQuantity) > 0 ? (acceptedWeightMax * Number(planning.sackQuantity) / 1000).toFixed(4) : planning.maximumSackWeight,
        comparison_quantity_pcs: comparisonPieces > 0 ? String(comparisonPieces) : '',
        quoted_same_quantity_weight: quotedSamePiecesKg > 0 ? quotedSamePiecesKg.toFixed(4) : '',
        production_same_quantity_weight: productionSamePiecesKg > 0 ? productionSamePiecesKg.toFixed(4) : '',
        acceptable_same_quantity_weight: acceptedSamePiecesMinKg > 0 ? `${acceptedSamePiecesMinKg.toFixed(4)} - ${acceptedSamePiecesMaxKg.toFixed(4)}` : '',
        same_quantity_weight_difference: comparisonPieces > 0 ? (productionSamePiecesKg - quotedSamePiecesKg).toFixed(4) : '',
        customer_spec_thickness: planning.salesThickness ? `${planning.salesThickness} • ${planning.salesThicknessMode}` : '',
        production_order_thickness: planning.thickness,
      })
      openSheet(sheet.html)
    } catch (e) {
      window.alert(e instanceof Error ? e.message : String(e))
    }
  }

  if (!labels) {
    return <p className="desk-wait">กำลังโหลด / loading...</p>
  }

  const display = answer?.display ?? {}
  const sellByKg = form.sale_basis === 'kg'
  const colors = labels.section_colors
  const quotedThicknessNumber = Number((planning.salesThickness.match(/[0-9.]+/) ?? ['0'])[0])
  const thicknessToleranceNumber = Number(planning.toleranceThickness)
  const referenceWeightNumber = Number(planning.referenceGramsPerItem)
  const acceptedWeightMin = quotedThicknessNumber > 0 && referenceWeightNumber > 0
    ? referenceWeightNumber * Math.max(0, quotedThicknessNumber - thicknessToleranceNumber) / quotedThicknessNumber : 0
  const acceptedWeightMax = quotedThicknessNumber > 0 && referenceWeightNumber > 0
    ? referenceWeightNumber * (quotedThicknessNumber + thicknessToleranceNumber) / quotedThicknessNumber : 0
  const comparisonPieces = Number(planning.sackQuantity)
  const quotedSamePiecesKg = comparisonPieces > 0 && referenceWeightNumber > 0 ? comparisonPieces * referenceWeightNumber / 1000 : 0
  const productionSamePiecesKg = comparisonPieces > 0 && Number(planning.gramsPerItem) > 0 ? comparisonPieces * Number(planning.gramsPerItem) / 1000 : 0
  const acceptedSamePiecesMinKg = comparisonPieces > 0 && acceptedWeightMin > 0 ? comparisonPieces * acceptedWeightMin / 1000 : 0
  const acceptedSamePiecesMaxKg = comparisonPieces > 0 && acceptedWeightMax > 0 ? comparisonPieces * acceptedWeightMax / 1000 : 0

  return (
    <div className="desk">
      <header className="desk-head">
        <div className="desk-head-left">
          <div className="desk-head-line">
            <h1>{labels.app_title}</h1>
            <span className="desk-state">{refText ?? labels.notes.unsaved}</span>
          </div>
          <p>{labels.header_subtitle}</p>
        </div>
        <div className="desk-who">
          <span className="desk-muted">{session.user.full_name || session.user.email}</span>
          <button type="button" className="desk-plain" onClick={onSignOut}>
            ออกจากระบบ / Sign out
          </button>
        </div>
      </header>

      {/* THE TOOLBAR WRAPS (FlowFrame): nine buttons in a fixed row is a row
          that runs off the edge of a narrow window. Sync/Server are not here:
          this screen IS the server - every save already lands on it. */}
      <div className="desk-actions">
        <nav className="desk-bar">
          <button type="button" onClick={newRecord}>
            {labels.buttons.new}
          </button>
          <button type="button" onClick={restoreDraft}>
            {labels.buttons.restore}
          </button>
          <button type="button" className="desk-accent" onClick={() => runCalculate()}>
            {labels.buttons.calculate}
          </button>
          <button type="button" className="desk-accent" onClick={keep} disabled={saving}>
            {labels.buttons.save}
          </button>
          <button type="button" onClick={printSummary}>
            {labels.buttons.print}
          </button>
          <button type="button" onClick={() => setHelpOpen(true)}>
            {labels.buttons.variables}
          </button>
        </nav>
        <p className="desk-status">{status ?? labels.notes.ready}</p>
      </div>

      <div className="desk-tabs" role="tablist">
        {(['pricing', 'sample', 'drawing', 'planning', 'coa', 'history'] as Tab[]).map((id) => (
          <button
            key={id}
            type="button"
            role="tab"
            aria-selected={tab === id}
            className={tab === id ? 'is-on' : ''}
            onClick={() => setTab(id)}
          >
            {id === 'coa' ? 'COA / Quality' : id === 'sample' ? 'Sample Inspection' : labels.tabs[id]}
          </button>
        ))}
      </div>

      {tab === 'pricing' && (
        <section className="desk-tabbody">
          {/* The compact card - the ONLY card the desktop's Pricing tab draws.
              Its section banner is deliberately removed (app.py:1006). */}
          <div className="desk-card is-compact">
            <div className="desk-formsection is-customer">
              <h2>1. ข้อมูลลูกค้าและเอกสาร / Customer & Document</h2>
            <div className="desk-row6">
              <Box label={labels.fields.customer_code}>
                <input
                  value={form.customer_code}
                  onChange={(e) => set({ customer_code: e.target.value })}
                />
              </Box>
              {/* NOT a <Box>. Box wraps its children in a <label>, and a label
                  makes every click inside it activate its control - so clicking
                  a suggestion would also be a click on the input. */}
              <div className="desk-box is-span2">
                <span className="desk-label">{labels.fields.customer}</span>
                <Suggest
                  label={labels.fields.customer}
                  value={form.customer}
                  onChange={(customer) => set({ customer })}
                  onPick={(customer_code) => set({ customer_code })}
                  rows={customers}
                />
              </div>
              <Box label={labels.fields.date}>
                <input
                  type="date"
                  value={form.quote_date}
                  onChange={(e) => set({ quote_date: e.target.value })}
                />
              </Box>
              <div className="desk-box is-span2">
                <span className="desk-label">{labels.fields.product_type}</span>
                <select
                  value={form.product_key}
                  onChange={(e) => {
                    const product_key = e.target.value as ProductKey
                    set({
                      product_key,
                      // Plastic Sheet is one layer; bags contain two sides.
                      // Other product types keep the operator's current choice.
                      ...(product_key === 'opaque' ? { thickness_mode: 'side' as const } : {}),
                      ...(['flat', 'gusset'].includes(product_key) ? { thickness_mode: 'pair' as const } : {}),
                    })
                  }}
                >
                  {Object.entries(meta?.products ?? {}).map(([key, label]) => (
                    <option key={key} value={key}>
                      {label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="desk-box is-span2">
                <span className="desk-label">{labels.fields.item_description}</span>
                <input value={form.item_description} onChange={(e) => set({ item_description: e.target.value })} />
              </div>
              <div className="desk-box is-span2">
                <span className="desk-label">{labels.fields.product_reference}</span>
                <input value={form.product_reference} onChange={(e) => set({ product_reference: e.target.value })} />
              </div>
            </div>
            </div>

            <div className="desk-formsection is-product">
              <h2>2. รายการสินค้า ขนาด และความหนา / Product, Dimensions & Thickness</h2>
            <div className="desk-row6">
              {drawn.includes('width') && (
                <Box label={labels.fields.width}>
                  <div className="desk-pair">
                    <input value={form.width} onChange={(e) => set({ width: e.target.value })} />
                    <select
                      value={form.width_unit}
                      onChange={(e) => set({ width_unit: e.target.value })}
                    >
                      {(meta?.dimension_units ?? []).map((u) => (
                        <option key={u}>{u}</option>
                      ))}
                    </select>
                  </div>
                </Box>
              )}
              {drawn.includes('length') && (
                <Box label={labels.fields.length}>
                  <div className="desk-pair">
                    <input value={form.length} onChange={(e) => set({ length: e.target.value })} />
                    <select
                      value={form.length_unit}
                      onChange={(e) => set({ length_unit: e.target.value })}
                    >
                      {(meta?.dimension_units ?? []).map((u) => (
                        <option key={u}>{u}</option>
                      ))}
                    </select>
                  </div>
                </Box>
              )}
              {drawn.includes('sold_length') && (
                <Box label={labels.fields.sold_length}>
                  <div className="desk-pair">
                    <input
                      value={form.sold_length}
                      onChange={(e) => set({ sold_length: e.target.value })}
                    />
                    <select
                      value={form.sold_length_unit}
                      onChange={(e) => set({ sold_length_unit: e.target.value })}
                    >
                      {(meta?.dimension_units ?? []).map((u) => (
                        <option key={u}>{u}</option>
                      ))}
                    </select>
                  </div>
                </Box>
              )}
              {drawn.includes('gusset') && (
                <Box label={labels.fields.gusset}>
                  <div className="desk-pair">
                    <input value={form.gusset} onChange={(e) => set({ gusset: e.target.value })} />
                    <select
                      value={form.width_unit}
                      onChange={(e) => set({ width_unit: e.target.value })}
                    >
                      {(meta?.dimension_units ?? []).map((u) => (
                        <option key={u}>{u}</option>
                      ))}
                    </select>
                  </div>
                </Box>
              )}
              {drawn.includes('height') && (
                <Box label={labels.fields.height}>
                  <div className="desk-pair">
                    <input value={form.height} onChange={(e) => set({ height: e.target.value })} />
                    <select
                      value={form.length_unit}
                      onChange={(e) => set({ length_unit: e.target.value })}
                    >
                      {(meta?.dimension_units ?? []).map((u) => (
                        <option key={u}>{u}</option>
                      ))}
                    </select>
                  </div>
                </Box>
              )}
              {drawn.includes('thickness') && (
                <Box label={labels.fields.thickness}>
                  <div className="desk-pair">
                    <input
                      value={form.thickness}
                      onChange={(e) => set({ thickness: e.target.value })}
                    />
                    <select
                      value={form.thickness_unit}
                      onChange={(e) => set({ thickness_unit: e.target.value })}
                    >
                      {(meta?.thickness_units ?? []).map((u) => (
                        <option key={u}>{u}</option>
                      ))}
                    </select>
                  </div>
                </Box>
              )}
            </div>

            <div className="desk-row6">
              {drawn.includes('thickness') && (
                <Box label={labels.fields.thickness_mode}>
                  <select
                    value={form.thickness_mode}
                    onChange={(e) => set({ thickness_mode: e.target.value as 'side' | 'pair' })}
                  >
                    {labels.choices.thickness_mode.map((c) => (
                      <option key={c.value} value={c.value}>
                        {c.label}
                      </option>
                    ))}
                  </select>
                </Box>
              )}
              {isBag && (
                <Box label={labels.fields.bottom_allowance}>
                  <input
                    value={form.bottom_allowance}
                    onChange={(e) => set({ bottom_allowance: e.target.value })}
                  />
                </Box>
              )}
            </div>
            <h3 className="desk-source-subhead"><span className="desk-newbadge">เพิ่มใหม่ / NEW</span> ค่าคลาดเคลื่อนและลักษณะพิเศษต้นทาง / Master Tolerances & Special Requirements</h3>
            <div className="desk-row6">
              <Box label="ความกว้าง ± mm / Width Tolerance"><input value={form.tolerance_width} onChange={(e) => set({ tolerance_width: e.target.value })} /></Box>
              <Box label="ความยาว ± mm / Length Tolerance"><input value={form.tolerance_length} onChange={(e) => set({ tolerance_length: e.target.value })} /></Box>
              <Box label="ความหนา ± mm / Thickness Tolerance"><input value={form.tolerance_thickness} onChange={(e) => set({ tolerance_thickness: e.target.value })} /></Box>
              {form.product_key === 'gusset' && <><Box label="พับข้างซ้าย ± mm / Left Gusset"><input value={form.tolerance_gusset_left} onChange={(e) => set({ tolerance_gusset_left: e.target.value })} /></Box><Box label="พับข้างขวา ± mm / Right Gusset"><input value={form.tolerance_gusset_right} onChange={(e) => set({ tolerance_gusset_right: e.target.value })} /></Box></>}
              <label className="desk-box is-span2"><span className="desk-label">ลักษณะงานพิเศษ บรรทัดละหนึ่งข้อ / Special Requirements</span><textarea rows={3} value={form.special_requirements} onChange={(e) => set({ special_requirements: e.target.value })} /></label>
            </div>
            </div>
          </div>

          {/* THE ACTION BAR, pinned under the form exactly as the desktop pins
              it to the bottom of the tab (app.py:1417-1641). */}
          <div className="desk-actionbar">
            <h2 className="desk-actiontitle">3. ข้อมูลราคาและแพ็คเกจ / Pricing & Packaging</h2>
            <div className="desk-steps" aria-label={labels.steps}>
              <span>1. กรอกสเปก / Enter Specs</span><b>›</b>
              <span>2. คำนวณ / Calculate</span><b>›</b>
              <span>3. กรอกราคาขาย / Final Price</span><b>›</b>
              <span>4. เก็บบันทึก / Save</span>
            </div>

            <div className="desk-basisrow">
              <select
                className="desk-basis"
                value={form.sale_basis}
                onChange={(e) =>
                  /* Changing the basis always turns the deduction back on -
                     the desktop's own rule (app.py:2744). */
                  set({ sale_basis: e.target.value as 'kg' | 'piece', apply_deduction: true })
                }
              >
                {labels.choices.sale_basis.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
              <p className="desk-primary">
                {display.primary_line || labels.primary_hints[form.sale_basis]}
              </p>
            </div>

            <div className="desk-factors">
              <Box label={labels.fields.density}>
                <input value={form.density} onChange={(e) => set({ density: e.target.value })} />
              </Box>
              <Box label={labels.fields.material_price}>
                <input
                  value={form.material_price}
                  onChange={(e) => set({ material_price: e.target.value })}
                />
              </Box>
              <Box label={labels.fields.markup}>
                <output>{liveMarkup(form)}</output>
              </Box>
              <div className="desk-box">
                <span className="desk-label">{labels.fields.deduction}</span>
                <div className="desk-pair">
                  <label className="desk-tick">
                    <input
                      type="checkbox"
                      checked={form.apply_deduction}
                      onChange={(e) => set({ apply_deduction: e.target.checked })}
                    />
                    {labels.fields.apply_deduction}
                  </label>
                  <span className="desk-label">{labels.fields.percent}</span>
                  <input
                    className="desk-narrow"
                    value={form.deduction}
                    onChange={(e) => set({ deduction: e.target.value })}
                  />
                </div>
              </div>
            </div>
            <p className="desk-mutednote">{labels.notes.markup}</p>

            <div className={sellByKg ? 'desk-prices is-kg' : 'desk-prices'}>
              {!sellByKg && (
                <div className="desk-price is-calculated">
                  <span>{labels.price_boxes.calculated}</span>
                  <output>{display.calculated_piece || '—'}</output>
                </div>
              )}
              {!sellByKg && (
                <label className="desk-price is-piece">
                  <span>{labels.price_boxes.final_piece}</span>
                  <input
                    value={form.price_per_piece}
                    onChange={(e) => set({ price_per_piece: e.target.value })}
                  />
                </label>
              )}
              <label className="desk-price is-kgbox">
                <span>
                  {sellByKg
                    ? labels.price_boxes.kg_when_selling_by_kg
                    : labels.price_boxes.kg_when_selling_by_piece}
                </span>
                <input
                  value={form.price_per_kg}
                  onChange={(e) => set({ price_per_kg: e.target.value })}
                />
              </label>
            </div>

            <div className="desk-subcard">
              <h3 className="desk-subhead">ข้อมูลแพ็คเกจที่เสนอขาย / Quoted Packaging</h3>
              <div className="desk-grid">
                <Box label="จำนวนใบต่อห่อหรือพับ / Pcs per Pack or Fold">
                  <input value={form.pack_quantity} onChange={(e) => set({ pack_quantity: e.target.value })} />
                </Box>
                <Box label="จำนวนใบรวมต่อกระสอบ / Total Pcs per Sack">
                  <input value={form.sack_quantity} onChange={(e) => set({ sack_quantity: e.target.value })} />
                </Box>
                <Box label="น้ำหนักต่อห่อหรือพับ / Pack or Fold Weight">
                  <output className="desk-greenout">{display.pack_weight || 'กดคำนวณเพื่อแสดง กก. / Calculate to show kg'}</output>
                </Box>
                <Box label="น้ำหนักต่อกระสอบ / Sack Weight">
                  <output className="desk-greenout">{display.sack_weight || 'กดคำนวณเพื่อแสดง กก. / Calculate to show kg'}</output>
                </Box>
              </div>
            </div>

            <div className="desk-keyresults" aria-label="Weight and production quantity results">
              <div className="desk-keyresult">
                <span>น้ำหนักต่อชิ้น / Weight per pc</span>
                <strong>{display.grams || '—'}</strong>
              </div>
              <div className="desk-keyresult">
                <span>จำนวนทางทฤษฎี / Theoretical quantity</span>
                <strong>{display.items_per_kg ? `${display.items_per_kg}/กก.` : '—'}</strong>
              </div>
              <div className="desk-keyresult">
                <span>
                  หลังหักเผื่อผลิต {form.apply_deduction ? form.deduction || '0' : '0'}% /
                  After production deduction
                </span>
                <strong>{display.adjusted_items ? `${display.adjusted_items}/กก.` : '—'}</strong>
              </div>
            </div>

            {!sellByKg && (
              <p className="desk-green">{display.derivation || labels.notes.derivation_idle}</p>
            )}
            <p className="desk-green">{answer?.human_summary || labels.notes.verification_idle}</p>
            <p className="desk-mutednote">
              {labels.notes.weight_formula_prefix}
              {answer?.formulas.weight ??
                meta?.default_weight_formulas[form.product_key] ??
                ''}
              {'\n'}
              {labels.notes.price_formula_prefix}
              {answer?.formulas.price ?? meta?.default_price_formula ?? ''}
            </p>
          </div>
        </section>
      )}

      {tab === 'planning' && (
        <section className="desk-tabbody">
          {/* Card 1 - the source picker (app.py:1122-1211). */}
          <div className="desk-card">
            <h2 className="desk-band" style={{ background: colors.production }}>
              {labels.sections.source}
            </h2>
            <SourcePicker
              labels={labels}
              value={planning.search}
              onChange={(search) => setPlanning((p) => ({ ...p, search }))}
              onLoad={loadPlanningSource}
            />
            <p className="desk-cardnote">{planning.summary || labels.planning.summary_idle}</p>
            <div className="desk-subcard">
              <h3 className="desk-subhead">ตารางเทียบสเปคลูกค้ากับสเปคสั่งผลิต / Customer Spec vs Production Order</h3>
              <p className="desk-cardnote">{planning.salesProduct || '—'} • {planning.salesPartNo || '—'}</p>
              <div className="desk-tablewrap"><table className="desk-table desk-comparetable"><thead><tr><th>ลำดับตรวจ / Check</th><th>ข้อมูลสั่งผลิตจริง / Production Order</th><th>สเปคที่ลูกค้ากำหนด / Customer-Specified</th><th>เกณฑ์ยอมรับได้ / Acceptance</th></tr></thead><tbody>
                <tr><th>1. ความหนา / Thickness</th><td><strong>{planning.thickness || '—'}</strong></td><td>{planning.salesThickness ? `${planning.salesThickness} • ${planning.salesThicknessMode}` : '—'}</td><td>{planning.toleranceThickness ? `±${planning.toleranceThickness} mm` : '—'}</td></tr>
                <tr><th>2. ความกว้าง / Width</th><td>{planning.width ? `${planning.width} cm` : '—'}</td><td>{planning.salesWidth || '—'}</td><td>{planning.toleranceWidth ? `±${planning.toleranceWidth} mm` : '—'}</td></tr>
                <tr><th>3. ความยาว / Length</th><td>{planning.length ? `${planning.length} cm` : '—'}</td><td>{planning.salesLength || '—'}</td><td>{planning.toleranceLength ? `±${planning.toleranceLength} mm` : '—'}</td></tr>
                <tr><th>4. แพ็คต่อกระสอบ / Packing</th><td>{planning.smallPackQuantity || '—'} {planning.saleBasis === 'piece' ? 'ใบ' : 'กก.'} × {planning.packageCountPerSack || '—'} {planning.packageStyle}</td><td>{planning.salesSize || '—'}</td><td>{planning.sackQuantity ? `${planning.sackQuantity} ใบ/กระสอบ` : '—'}</td></tr>
                <tr><th>5. น้ำหนักต่อใบ / Weight per pc</th><td><strong>{planning.gramsPerItem ? `${planning.gramsPerItem} g/pc` : '—'}</strong></td><td>{planning.referenceGramsPerItem ? `${planning.referenceGramsPerItem} g/pc` : '—'}</td><td>{acceptedWeightMin > 0 ? `${acceptedWeightMin.toFixed(3)} - ${acceptedWeightMax.toFixed(3)} g/pc` : '—'}</td></tr>
                <tr><th>6. เทียบจำนวนใบเท่ากัน / Same Quantity</th><td><strong>{comparisonPieces > 0 ? `${comparisonPieces} pcs = ${productionSamePiecesKg.toFixed(4)} kg` : '—'}</strong></td><td>{comparisonPieces > 0 ? `${comparisonPieces} pcs = ${quotedSamePiecesKg.toFixed(4)} kg` : '—'}</td><td>{acceptedSamePiecesMinKg > 0 ? `${acceptedSamePiecesMinKg.toFixed(4)} - ${acceptedSamePiecesMaxKg.toFixed(4)} kg` : '—'}</td></tr>
                <tr><th>7. ผลต่างน้ำหนัก / Weight Difference</th><td colSpan={2}>{comparisonPieces > 0 ? `${(productionSamePiecesKg - quotedSamePiecesKg).toFixed(4)} kg สำหรับ ${comparisonPieces} ใบ / pcs` : '—'}</td><td>{productionSamePiecesKg >= acceptedSamePiecesMinKg && productionSamePiecesKg <= acceptedSamePiecesMaxKg && comparisonPieces > 0 ? 'PASS' : '—'}</td></tr>
              </tbody></table></div>
            </div>
            <div className="desk-subcard">
              <h3 className="desk-subhead">ข้อมูลรายการที่ใช้สั่งผลิตจริง (กรอกหรือปรับได้) / Production Order Specification</h3>
            <div className="desk-grid">
              <Box label={labels.planning.fields.production_width}>
                <input
                  value={planning.width}
                  onChange={(e) => setPlanning((p) => ({ ...p, width: e.target.value }))}
                />
              </Box>
              <Box label={labels.planning.fields.production_length}>
                <input
                  value={planning.length}
                  onChange={(e) => setPlanning((p) => ({ ...p, length: e.target.value }))}
                />
              </Box>
              <Box label={labels.planning.fields.production_thickness}>
                <input
                  value={planning.thickness}
                  onChange={(e) => setPlanning((p) => ({ ...p, thickness: e.target.value }))}
                />
              </Box>
              <Box label={labels.planning.fields.production_gusset}>
                <input
                  value={planning.gusset}
                  onChange={(e) => setPlanning((p) => ({ ...p, gusset: e.target.value }))}
                />
              </Box>
              <Box label={labels.planning.fields.packaging}>
                <input
                  value={planning.packaging}
                  onChange={(e) => setPlanning((p) => ({ ...p, packaging: e.target.value }))}
                />
              </Box>
              <Box label={labels.planning.fields.fixed_qty}>
                <input
                  value={planning.quantity}
                  onChange={(e) => setPlanning((p) => ({ ...p, quantity: e.target.value }))}
                />
              </Box>
              <Box label="จำนวนใบต่อกระสอบ / Pcs per sack">
                <input
                  value={planning.sackQuantity}
                  onChange={(e) => {
                    const sackQuantity = e.target.value
                    const weight = Number(sackQuantity) * Number(planning.gramsPerItem) / 1000
                    setPlanning((p) => ({ ...p, sackQuantity,
                      sackWeight: Number.isFinite(weight) && weight > 0 ? weight.toFixed(4) : '' }))
                  }}
                />
              </Box>
              <Box label="น้ำหนักต่อกระสอบ / Sack weight (kg)">
                <output className="desk-greenout">{planning.sackWeight ? `${planning.sackWeight} กก.` : '—'}</output>
              </Box>
              <Box label="หน่วยขาย / Sale Basis">
                <select value={planning.saleBasis} onChange={(e) => setPlanning((p) => ({ ...p, saleBasis: e.target.value as 'piece' | 'kg' }))}>
                  <option value="piece">ขายเป็นใบ / Sell by Piece</option><option value="kg">ขายเป็นกิโลกรัม / Sell by kg</option>
                </select>
              </Box>
              <Box label="รูปแบบแพ็ค / Packing Style">
                <select value={planning.packageStyle} onChange={(e) => setPlanning((p) => ({ ...p, packageStyle: e.target.value as PlanningState['packageStyle'] }))}>
                  <option value="ห่อ / Pack">ห่อ / Pack</option><option value="พับ / Fold">พับ / Fold</option>
                </select>
              </Box>
              <Box label="เลือกข้อมูลแพ็คสำหรับผลิต / Production Packing Source">
                <select value={planning.packagingChoice} onChange={(e) => setPlanning((p) => {
                  const packagingChoice = e.target.value as 'quoted' | 'new'
                  if (packagingChoice === 'quoted') {
                    const total = Number(p.quotedSmallPackQuantity) * Number(p.quotedPackageCountPerSack)
                    return { ...p, packagingChoice, smallPackQuantity: p.quotedSmallPackQuantity,
                      packageCountPerSack: p.quotedPackageCountPerSack,
                      sackQuantity: p.saleBasis === 'piece' && total > 0 ? String(total) : p.sackQuantity,
                      sackWeight: total > 0 ? (p.saleBasis === 'piece' ? (total * Number(p.gramsPerItem) / 1000).toFixed(4) : total.toFixed(4)) : '' }
                  }
                  return { ...p, packagingChoice, smallPackQuantity: '', packageCountPerSack: '', sackQuantity: '', sackWeight: '' }
                })}>
                  <option value="quoted">ใช้ตามที่คำนวณและเสนอขาย / Use Quoted Packaging</option>
                  <option value="new">ลูกค้าขอเปลี่ยน - ป้อนข้อมูลใหม่ / Customer Change</option>
                </select>
              </Box>
              <Box label={planning.saleBasis === 'piece' ? 'จำนวนใบต่อห่อหรือพับ / Pcs per Pack or Fold' : 'น้ำหนักต่อห่อหรือพับ / kg per Pack or Fold'}>
                <input value={planning.smallPackQuantity} readOnly={planning.packagingChoice === 'quoted'} onChange={(e) => setPlanning((p) => {
                  const smallPackQuantity = e.target.value, total = Number(smallPackQuantity) * Number(p.packageCountPerSack)
                  return { ...p, smallPackQuantity,
                    sackQuantity: p.saleBasis === 'piece' && total > 0 ? String(total) : p.sackQuantity,
                    sackWeight: total > 0 ? (p.saleBasis === 'piece' ? (total * Number(p.gramsPerItem) / 1000).toFixed(4) : total.toFixed(4)) : '' }
                })} />
              </Box>
              <Box label="จำนวนห่อหรือพับต่อกระสอบ / Packs or Folds per Sack">
                <input value={planning.packageCountPerSack} readOnly={planning.packagingChoice === 'quoted'} onChange={(e) => setPlanning((p) => {
                  const packageCountPerSack = e.target.value, total = Number(p.smallPackQuantity) * Number(packageCountPerSack)
                  return { ...p, packageCountPerSack,
                    sackQuantity: p.saleBasis === 'piece' && total > 0 ? String(total) : p.sackQuantity,
                    sackWeight: total > 0 ? (p.saleBasis === 'piece' ? (total * Number(p.gramsPerItem) / 1000).toFixed(4) : total.toFixed(4)) : '' }
                })} />
              </Box>
              <Box label={planning.saleBasis === 'piece' ? 'รวมจำนวนใบต่อกระสอบ / Total Pcs per Sack' : 'รวมน้ำหนักต่อกระสอบ / Total kg per Sack'}>
                <output className="desk-greenout">{Number(planning.smallPackQuantity) > 0 && Number(planning.packageCountPerSack) > 0 ? `${Number(planning.smallPackQuantity) * Number(planning.packageCountPerSack)} ${planning.saleBasis === 'piece' ? 'ใบ' : 'กก.'}` : '—'}</output>
              </Box>
              {planning.saleBasis === 'kg' && <Box label="น้ำหนักสูงสุดที่อนุญาต / Maximum Sack Weight (kg)">
                <input value={planning.maximumSackWeight} onChange={(e) => setPlanning((p) => ({ ...p, maximumSackWeight: e.target.value }))} placeholder="กรอกตามข้อตกลงลูกค้า / Enter agreed limit" />
              </Box>}
              <Box label={labels.planning.fields.production_notes}>
                <input
                  value={planning.notes}
                  onChange={(e) => setPlanning((p) => ({ ...p, notes: e.target.value }))}
                />
              </Box>
              <Box label="เลขแบบอนุมัติ / Approved Drawing No.">
                <output className="desk-greenout">{planning.drawingDocNo || '— ยังไม่มีแบบที่บันทึกและผูกกับใบราคานี้ —'}</output>
              </Box>
              <label className="desk-box" style={{ gridColumn: '1 / -1' }}>
                <span className="desk-label">ลักษณะพิเศษจากแบบที่ลูกค้าอนุมัติ / Approved Special Characteristics</span>
                <textarea rows={4} value={planning.specialFeatures} readOnly placeholder="บันทึก Drawing โดยอ้างอิงเลขใบคำนวณราคาก่อน ข้อมูลจะขึ้นอัตโนมัติที่นี่" />
                <span className="desk-hint">ข้อมูลควบคุมจาก Drawing ไม่ให้แผนกตัดพิมพ์ซ้ำหรือแก้ต่างจากแบบอนุมัติ</span>
              </label>
              <div className="desk-box is-button">
                <button type="button" className="desk-accent" onClick={compareWeight}>
                  {labels.planning.compare}
                </button>
              </div>
            </div>
            </div>
            <div className="desk-subcard">
              <h3 className="desk-subhead">ค่าความคลาดเคลื่อนจากใบเสนอราคา / Quotation tolerances</h3>
              <div className="desk-grid">
                <Box label="ความกว้าง ± mm / Width">
                  <input value={planning.toleranceWidth} readOnly />
                </Box>
                <Box label="ความยาว ± mm / Length">
                  <input value={planning.toleranceLength} readOnly />
                </Box>
                <Box label="ความหนา ± mm / Thickness">
                  <input value={planning.toleranceThickness} readOnly />
                </Box>
                {planning.productKey === 'gusset' && <>
                  <Box label="พับข้างซ้าย ± mm / Left gusset">
                    <input value={planning.toleranceGussetLeft} onChange={(e) => setPlanning((p) => ({ ...p, toleranceGussetLeft: e.target.value }))} />
                  </Box>
                  <Box label="พับข้างขวา ± mm / Right gusset">
                    <input value={planning.toleranceGussetRight} onChange={(e) => setPlanning((p) => ({ ...p, toleranceGussetRight: e.target.value }))} />
                  </Box>
                </>}
              </div>
              <div className="desk-tablewrap"><table className="desk-table desk-qctable"><thead><tr><th>รายการวัด / QC Check</th><th>ค่าที่ใช้ผลิต / Nominal</th><th>ช่วงยอมรับได้ / Acceptable Range</th><th>ค่าที่วัดได้ / Actual</th><th>ผล / Result</th></tr></thead><tbody>
                <tr><td>ความกว้าง / Width</td><td>{planning.width ? `${Number(planning.width) * 10} mm` : '—'}</td><td>{Number(planning.width) > 0 ? `${Number(planning.width) * 10 - Number(planning.toleranceWidth)} - ${Number(planning.width) * 10 + Number(planning.toleranceWidth)} mm` : '—'}</td><td></td><td>☐ PASS ☐ FAIL</td></tr>
                <tr><td>ความยาว / Length</td><td>{planning.length ? `${Number(planning.length) * 10} mm` : '—'}</td><td>{Number(planning.length) > 0 ? `${Number(planning.length) * 10 - Number(planning.toleranceLength)} - ${Number(planning.length) * 10 + Number(planning.toleranceLength)} mm` : '—'}</td><td></td><td>☐ PASS ☐ FAIL</td></tr>
                <tr><td>ความหนา / Thickness</td><td>{planning.thickness ? `${planning.thickness} mm` : '—'}</td><td>{Number(planning.thickness) > 0 ? `${(Number(planning.thickness) - Number(planning.toleranceThickness)).toFixed(3)} - ${(Number(planning.thickness) + Number(planning.toleranceThickness)).toFixed(3)} mm` : '—'}</td><td></td><td>☐ PASS ☐ FAIL</td></tr>
                {planning.productKey === 'gusset' && <tr><td>พับข้างซ้าย/ขวา / Gusset L/R</td><td>{planning.gusset ? `${Number(planning.gusset) * 10} mm` : '—'}</td><td>ซ้าย ±{planning.toleranceGussetLeft || '—'} / ขวา ±{planning.toleranceGussetRight || '—'} mm</td><td></td><td>☐ PASS ☐ FAIL</td></tr>}
              </tbody></table></div>
            </div>
            <div className="desk-keyresults" aria-label="Production planning results">
              <div className="desk-keyresult"><span>น้ำหนักต่อชิ้น / Weight per pc</span><strong>{planning.gramsPerItem ? `${planning.gramsPerItem} กรัม` : '—'}</strong></div>
              <div className="desk-keyresult"><span>จำนวนทางทฤษฎี / Theoretical quantity</span><strong>{planning.itemsPerKg ? `${planning.itemsPerKg} ใบ/กก.` : '—'}</strong></div>
              <div className="desk-keyresult"><span>จำนวนหลังหักเผื่อผลิต / After production deduction</span><strong>{planning.adjustedItems ? `${planning.adjustedItems} ใบ/กก.` : '—'}</strong></div>
              <div className="desk-keyresult"><span>จำนวนต่อกระสอบ / Pcs per sack</span><strong>{planning.sackQuantity ? `${planning.sackQuantity} ใบ` : '—'}</strong></div>
              <div className="desk-keyresult"><span>น้ำหนักต่อกระสอบ / Sack weight</span><strong>{planning.sackWeight ? `${planning.sackWeight} กก.` : '—'}</strong></div>
            </div>
            <p className="desk-green">{planning.compare || labels.planning.compare_idle}</p>
            <p className="desk-mutednote">{labels.planning.next_note}</p>
          </div>

          {/* Card 2 - Production Planning Details: a notebook whose one tab is
              the production panel (app.py:972-984, 1717-1871). */}
          <div className="desk-card">
            <h2 className="desk-band" style={{ background: colors.calculation }}>
              {labels.sections.planning}
            </h2>
            <div className="desk-tabs is-inner">
              <button type="button" className="is-on">
                {labels.sections.planning_tab}
              </button>
            </div>
            <div className="desk-panel">
              <h3 className="desk-band is-tight" style={{ background: colors.production }}>
                {labels.sections.production}
              </h3>
              <div className="desk-grid">
                <Box label={labels.fields.deduction_full}>
                  <input
                    value={form.deduction}
                    onChange={(e) => set({ deduction: e.target.value })}
                  />
                </Box>
                <Box label={labels.fields.order_qty}>
                  <input
                    value={form.order_quantity}
                    onChange={(e) => set({ order_quantity: e.target.value })}
                  />
                </Box>
                <Box label={labels.fields.control_min}>
                  <input
                    value={form.control_min}
                    onChange={(e) => set({ control_min: e.target.value })}
                  />
                </Box>
                <Box label={labels.fields.control_max}>
                  <input
                    value={form.control_max}
                    onChange={(e) => set({ control_max: e.target.value })}
                  />
                </Box>
              </div>
              <div className="desk-subcard">
                <div className="desk-grid">
                  <Box label={labels.fields.pack_qty}>
                    <input
                      value={form.pack_quantity}
                      onChange={(e) => set({ pack_quantity: e.target.value })}
                    />
                  </Box>
                  <Box label={labels.fields.sack_qty}>
                    <input
                      value={form.sack_quantity}
                      onChange={(e) => set({ sack_quantity: e.target.value })}
                    />
                  </Box>
                  <div className="desk-box">
                    <span className="desk-label">{labels.sections.deduction_box}</span>
                    <label className="desk-tick">
                      <input
                        type="checkbox"
                        checked={form.apply_deduction}
                        onChange={(e) => set({ apply_deduction: e.target.checked })}
                      />
                      {labels.sections.apply_deduction_above}
                    </label>
                    <span className="desk-hint">{labels.notes.deduction}</span>
                  </div>
                </div>
              </div>
              {form.product_key === 'cover' && (
                <div className="desk-grid">
                  <Box label={labels.fields.roof_gsm}>
                    <input
                      value={form.roof_gsm}
                      onChange={(e) => set({ roof_gsm: e.target.value })}
                    />
                  </Box>
                  <Box label={labels.fields.mesh_gsm}>
                    <input
                      value={form.mesh_gsm}
                      onChange={(e) => set({ mesh_gsm: e.target.value })}
                    />
                  </Box>
                  <Box label={labels.fields.roof_area}>
                    <output className="desk-greenout">{display.roof_area || '—'}</output>
                  </Box>
                  <Box label={labels.fields.mesh_area}>
                    <output className="desk-greenout">{display.mesh_area || '—'}</output>
                  </Box>
                </div>
              )}
              <div className="desk-formula">
                <span className="desk-subhead">{labels.fields.weight_formula}</span>
                <textarea
                  rows={2}
                  spellCheck={false}
                  value={form.weight_formula}
                  placeholder={meta?.default_weight_formulas[form.product_key] ?? ''}
                  onChange={(e) => set({ weight_formula: e.target.value })}
                />
                <div className="desk-formula-reset">
                  <button type="button" onClick={() => set({ weight_formula: '' })}>
                    {labels.buttons.reset_formula}
                  </button>
                </div>
              </div>
              <div className="desk-results">
                {labels.results.filter((tile) => tile.key !== 'total_price').map((tile) => (
                  <div key={tile.key} className="desk-result">
                    <span className="desk-resultname">
                      {tile.live_label === 'deduction_caption'
                        ? display.deduction_caption || deductionCaption(labels, form)
                        : tile.label}
                    </span>
                    <strong>{display[tile.key] || '—'}</strong>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Card 3 - the shop-floor work orders (app.py:1325-1361). */}
          <div className="desk-card">
            <h2 className="desk-band" style={{ background: colors.production }}>
              {labels.sections.work_orders}
            </h2>
            <div className="desk-tabs is-inner">
              {(['blown', 'cutting'] as const).map((dept) => (
                <button
                  key={dept}
                  type="button"
                  className={workDept === dept ? 'is-on' : ''}
                  onClick={() => setWorkDept(dept)}
                >
                  {labels.work_orders.tabs[dept]}
                </button>
              ))}
            </div>
            <div className="desk-panel">
              <p className="desk-cardnote">{labels.work_orders.note}</p>
              <div className="desk-buttonrow">
                <button type="button" onClick={() => copyWorkOrder(workDept)}>
                  {labels.work_orders.copy[workDept]}
                </button>
                <button
                  type="button"
                  className="desk-accent"
                  onClick={() => printWorkOrder(workDept)}
                >
                  {labels.work_orders.print[workDept]}
                </button>
              </div>
            </div>
          </div>
        </section>
      )}

      {tab === 'drawing' && (
        <Drawing labels={labels} form={form} meta={meta} customers={customers} />
      )}

      {tab === 'sample' && <SampleInspection />}

      {tab === 'coa' && <Coa />}

      {tab === 'history' && (
        <History
          labels={labels}
          products={meta?.products ?? {}}
          customers={customers}
          onEdit={editFromHistory}
          onStatus={setStatus}
          bridgeOn={meta?.pacos_bridge ?? false}
        />
      )}

      {helpOpen && meta && <Formulas meta={meta} onClose={() => setHelpOpen(false)} />}
    </div>
  )
}

/* The planning tab's source picker: an entry whose suggestions come from the
 * server per keystroke, a ▼ that opens the newest records, and the Load
 * button (app.py:1136-1165, widgets.py SuggestEntry). */
function SourcePicker({
  labels,
  value,
  onChange,
  onLoad,
}: {
  labels: Labels
  value: string
  onChange: (value: string) => void
  onLoad: () => void
}) {
  const [rows, setRows] = useState<SourceRow[]>([])
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(0)
  const timer = useRef(0)
  const inFlight = useRef<AbortController | null>(null)
  const typed = useRef(false)

  function fetchRows(q: string, show: boolean) {
    inFlight.current?.abort()
    const ac = new AbortController()
    inFlight.current = ac
    planningSources(q, ac.signal)
      .then((answer) => {
        if (ac.signal.aborted) return
        setRows(answer.rows)
        setActive(0)
        if (show) setOpen(answer.rows.length > 0)
      })
      .catch(() => {
        /* A suggestion list is a convenience. It must never be the reason a
           record cannot be found by typing its reference. */
        if (!ac.signal.aborted) setOpen(false)
      })
  }

  useEffect(() => {
    if (!typed.current) return
    typed.current = false
    window.clearTimeout(timer.current)
    const q = value.trim()
    timer.current = window.setTimeout(() => fetchRows(q, q.length > 0), 200)
    return () => window.clearTimeout(timer.current)
  }, [value])

  function choose(row: SourceRow) {
    onChange(row.line)
    setOpen(false)
  }

  return (
    <div className="desk-source">
      <span className="desk-label">{labels.planning.find}</span>
      <div className="desk-sourcerow">
        <div className="desk-sourcebox">
          <input
            value={value}
            role="combobox"
            aria-expanded={open}
            aria-label={labels.planning.find}
            onChange={(e) => {
              typed.current = true
              onChange(e.target.value)
            }}
            onKeyDown={(e) => {
              if (e.key === 'ArrowDown') {
                e.preventDefault()
                if (!open) fetchRows(value.trim(), true)
                else setActive((i) => Math.min(i + 1, rows.length - 1))
              } else if (e.key === 'ArrowUp') {
                e.preventDefault()
                setActive((i) => Math.max(i - 1, 0))
              } else if (e.key === 'Enter' && open && rows[active]) {
                e.preventDefault()
                choose(rows[active])
              } else if (e.key === 'Escape') {
                setOpen(false)
              }
            }}
            onBlur={() => window.setTimeout(() => setOpen(false), 120)}
          />
          {open && (
            <ul className="desk-suggest" role="listbox">
              {rows.map((row, i) => (
                <li
                  key={row.quote_ref}
                  role="option"
                  aria-selected={i === active}
                  className={i === active ? 'is-active' : ''}
                  onMouseDown={(e) => {
                    e.preventDefault()
                    choose(row)
                  }}
                >
                  {row.line}
                </li>
              ))}
            </ul>
          )}
        </div>
        {/* The ▼ opens the list with the newest records before anything is
            typed - and it is a Segoe UI glyph on the desktop because
            Leelawadee UI has no arrows (app.py:298-303). */}
        <button
          type="button"
          className="desk-glyph"
          aria-label={labels.planning.find}
          onClick={() => fetchRows(value.trim(), true)}
        >
          ▼
        </button>
        <button type="button" className="desk-accent desk-load" onClick={onLoad}>
          {labels.planning.load}
        </button>
      </div>
    </div>
  )
}

/* A caption, a box, and a note that is ALWAYS VISIBLE - never a tooltip
 * (LAW P9). If a note matters enough to write, it matters enough to show. */
function Box({
  label,
  note,
  children,
}: {
  label: string
  note?: string
  children: React.ReactNode
}) {
  return (
    <label className="desk-box">
      <span className="desk-label">{label}</span>
      {children}
      {note && <span className="desk-hint">{note}</span>}
    </label>
  )
}
