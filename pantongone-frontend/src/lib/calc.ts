/* The shapes the calculation endpoint takes and gives back.
 *
 * A mirror of api/main.py's CalcRequest, field for field. It is written out
 * rather than left loose because the two have to agree exactly: a field added
 * on one side and forgotten on the other is a box somebody fills in that never
 * reaches the arithmetic, and nothing says so.
 *
 * Units travel as the Thai words the desktop program uses - "ซม.", "มม.",
 * "เมตร" - because that is what its unit pickers hold and what the server
 * validates against. Converting them to codes here would be a second
 * vocabulary to keep in step for no gain (LAW P11: convert at the boundary,
 * and the boundary is the server).
 */

export type Measure = { value: number; unit: string }
export type Thickness = { value: number; unit: string; mode: 'side' | 'pair' }

export type ProductKey = 'flat' | 'sleeve' | 'opaque' | 'gusset' | 'roll' | 'cover'

export const PRODUCT_ORDER: ProductKey[] = ['flat', 'gusset', 'sleeve', 'opaque', 'roll', 'cover']

export function orderedProducts(products: Record<string, string> = {}): [ProductKey, string][] {
  const complete: Record<string, string> = {
    ...products,
    sleeve: products.sleeve ?? 'ปลอกพลาสติกเปิดสองด้าน (Open-Ended Plastic Sleeve)',
  }
  return PRODUCT_ORDER
    .map((key): [ProductKey, string] => [key, complete[key] ?? ''])
    .filter((row) => Boolean(row[1]))
}

export type CalcRequest = {
  product_key: ProductKey
  width: Measure
  length: Measure
  height: Measure
  gusset: Measure
  sold_length: Measure
  bottom_allowance: Measure
  thickness: Thickness
  length_reference: string
  density_g_cm3: number
  material_price_per_kg: number
  deduction_percent: number
  apply_deduction: boolean
  sale_basis: 'kg' | 'piece'
  selling_price_per_piece_override: number
  selling_price_per_kg_override: number
  pack_quantity: number
  sack_quantity: number
  order_quantity: number
  control_min_g: number
  control_max_g: number
  roof_gsm: number
  mesh_gsm: number
  weight_formula: string
  price_formula: string
  tolerance_width: Measure
  tolerance_length: Measure
  tolerance_thickness: Measure
  tolerance_gusset_left: Measure
  tolerance_gusset_right: Measure
  special_requirements: string
}

/** Every figure the screen prints, already formatted by the server - "12.345
 *  กรัม", not 12.3449999. The desktop rounds in one place and so does this. */
export type CalcResponse = {
  results: Record<string, number | string>
  normalized: Record<string, number | string>
  display: Record<string, string>
  human_summary: string
  price_basis: string
  formulas: Record<string, string>
}

export type QuoteRow = {
  quote_ref: string
  quote_date: string
  customer: string
  customer_code: string
  item_description: string
  product_label: string
  size_text: string
  grams_per_item: number
  unit_price: number
  total_price: number
  [key: string]: unknown
}

/* The pricing form, held as text.
 *
 * It lives HERE rather than in the panel that draws it because the drawing
 * screen reads the same sizes - a drawing that says 400 mm for a bag priced at
 * 420 is worse than no drawing, since both get signed. Keeping the type where
 * both can see it is what stops the two screens growing their own idea of what
 * a width is.
 */
export type Form = {
  customer: string
  customer_code: string
  quote_date: string
  item_description: string
  product_reference: string

  product_key: ProductKey
  width: string
  width_unit: string
  length: string
  length_unit: string
  height: string
  gusset: string
  sold_length: string
  sold_length_unit: string
  thickness: string
  thickness_unit: string
  thickness_mode: 'side' | 'pair'
  bottom_allowance: string
  length_reference: string

  density: string
  material_price: string
  deduction: string
  apply_deduction: boolean
  sale_basis: 'kg' | 'piece'
  price_per_kg: string
  price_per_piece: string

  order_quantity: string
  pack_quantity: string
  sack_quantity: string
  control_min: string
  control_max: string

  /** The cover product weighs roof and mesh by GSM; every other product
   *  ignores these. The desktop's own defaults are 120 and 80. */
  roof_gsm: string
  mesh_gsm: string

  /** Empty means "the default for this product", which lives on the server
   *  with the formulas themselves (LAW P1). */
  weight_formula: string
  price_formula: string
  tolerance_width: string
  tolerance_length: string
  tolerance_thickness: string
  tolerance_gusset_left: string
  tolerance_gusset_right: string
  special_requirements: string
}

export type DrawingRequest = {
  drawing_view?: '2d' | '3d' | 'both'
  product_key: ProductKey
  doc_no: string
  customer: string
  customer_code: string
  title: string
  part_no: string
  revision: string
  date: string
  material: string
  color: string
  printing: string
  width: Measure
  length: Measure
  height: Measure
  gusset: Measure
  thickness: Thickness
  tol_dim_lo: number
  tol_dim_hi: number
  tol_thickness: number
  length_datum: string
  display_unit: 'mm' | 'inch'
  holes_count: number
  holes_dia: string
  label_w: number
  label_h: number
  extra_notes: string[]
}
