import type { CalcRequest, CalcResponse, DrawingRequest, QuoteRow } from './calc'

/* The one way this app talks to the server.
 *
 * Sixty lines and no axios: fetch is already in the browser, and what this
 * needs beyond it is a token header and one place that notices a 401. A
 * library would bring interceptors, cancellation and a retry policy none of
 * which this uses (tech-stack.md 2).
 *
 * NOTHING HERE CALCULATES. Every figure on screen is one the server worked out
 * from the desktop program's own calculator.py, so the browser cannot drift
 * from the .exe (LAW P1, LAW K1). The types below say what comes back; they do
 * not say how it was arrived at, because that is not this side's business.
 */

const TOKEN_KEY = 'pantongone.token'
const USER_KEY = 'pantongone.user'

/* permissions: what the server will let this account do - PacOs's ticks for a
 * PacOs account, every key for a local one. lib/permissions.ts reads them to
 * hide the tabs and buttons that would only be refused. */
export type User = { id: number; email: string; full_name: string; permissions?: string[] }

export type Session = { token: string; expires_at: number; user: User }

/* Called when the server says the token is no longer good. App.tsx registers
 * the handler that puts the sign-in screen back up - the alternative is every
 * caller remembering to check, and the one that forgets leaves somebody
 * clicking a dead screen. */
let onSignedOut: (() => void) | null = null
export function setSignedOutHandler(fn: () => void) {
  onSignedOut = fn
}

export function storedSession(): Session | null {
  try {
    const token = localStorage.getItem(TOKEN_KEY)
    const raw = localStorage.getItem(USER_KEY)
    if (!token || !raw) return null
    const held = JSON.parse(raw) as { user: User; expires_at: number }
    /* An expired token is treated as no token at all rather than sent and
     * refused. The screen it would have drawn for half a second is a screen
     * showing somebody else's last session. */
    if (held.expires_at * 1000 < Date.now()) return null
    return { token, user: held.user, expires_at: held.expires_at }
  } catch {
    // A private window, or storage turned off. Signing in again is the whole
    // cost, and it must not be a blank page.
    return null
  }
}

function remember(session: Session) {
  try {
    localStorage.setItem(TOKEN_KEY, session.token)
    localStorage.setItem(
      USER_KEY,
      JSON.stringify({ user: session.user, expires_at: session.expires_at }),
    )
  } catch {
    /* Not being able to remember is not a reason to refuse the sign-in that
     * just succeeded: this session keeps working, the next one asks again. */
  }
}

export function forget() {
  try {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  } catch {
    /* nothing to clear */
  }
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const held = storedSession()
  const headers = new Headers(init.headers)
  if (init.body) headers.set('content-type', 'application/json')
  if (held) headers.set('authorization', `Bearer ${held.token}`)

  const answer = await fetch(path, { ...init, headers })
  if (answer.status === 401 && held) {
    // The token this app was holding is no longer good. Clearing it here rather
    // than in the caller means every screen behaves the same way at the moment
    // a session ends.
    forget()
    onSignedOut?.()
  }
  if (!answer.ok) {
    /* THE SERVER'S OWN SENTENCE, NOT A CODE. It answers in Thai and English
     * both - "อีเมลหรือรหัสผ่านไม่ถูกต้อง / that email and password do not
     * match" - and replacing that with "Error 401" would be this screen
     * throwing away the only part a person can act on. */
    let message = `${answer.status}`
    try {
      const body = (await answer.json()) as { error?: string; detail?: string }
      message = body.error || body.detail || message
    } catch {
      /* an answer that is not JSON - a proxy page, most likely */
    }
    throw new ApiError(answer.status, message)
  }
  if (answer.status === 204) return undefined as T
  return (await answer.json()) as T
}

export async function signIn(email: string, password: string): Promise<Session> {
  const session = await request<Session>('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  })
  remember(session)
  return session
}

export function signOut() {
  forget()
  onSignedOut?.()
}

/* The held session's permissions, asked again instead of trusted from the
 * last sign-in: a session kept from before a release that added screens must
 * not open on a desk with every tab hidden. */
export async function refreshUser(session: Session): Promise<Session> {
  const next = { ...session, user: await getMe() }
  remember(next)
  return next
}

// ---------------------------------------------------------------- the screen

/* Every word the desktop screen prints, served by the API.
 *
 * They are NOT held here. api/screen.py lifted them from app.py verbatim, and
 * a copy in the browser would be a second place for them to be wrong - the one
 * that nobody re-reads when the desktop wording changes. The shape is loose on
 * purpose: this side draws whatever it is given. */

/* The keys are written out rather than left as a bare string index, and that is
 * the point of them: a key renamed in api/screen.py and not here becomes a
 * compile error instead of a caption that silently draws nothing. They are the
 * contract between the two files. */
export type FieldKey =
  | 'customer_code' | 'customer' | 'date' | 'product_type' | 'item_description'
  | 'product_reference' | 'width' | 'length' | 'gusset' | 'height' | 'sold_length'
  | 'thickness' | 'thickness_mode' | 'bottom_allowance' | 'length_reference'
  | 'sale_basis' | 'density' | 'material_price' | 'markup' | 'deduction'
  | 'apply_deduction' | 'order_qty' | 'deduction_full' | 'control_min'
  | 'control_max' | 'pack_qty' | 'sack_qty' | 'roof_gsm' | 'mesh_gsm'
  | 'roof_area' | 'mesh_area' | 'weight_formula' | 'price_formula'
  | 'tol_width' | 'tol_length' | 'tol_thickness'
  | 'customer_full' | 'date_full' | 'product_type_full' | 'item_full'
  | 'part_full' | 'image' | 'percent'

export type NoteKey =
  | 'markup' | 'thickness_mode' | 'allowance' | 'allowance_roll' | 'allowance_cover'
  | 'tolerance' | 'deduction' | 'deduction_caption' | 'deduction_caption_off'
  | 'related_idle' | 'related_none' | 'verification_idle' | 'derivation_idle'
  | 'ready' | 'calculated_ok' | 'check_input' | 'formula_help' | 'not_saved'
  | 'unsaved' | 'weight_formula_prefix' | 'price_formula_prefix'
  | 'quote_ref_prefix' | 'saved_status_prefix' | 'saved_title' | 'saved_body'
  | 'need_customer' | 'need_customer_code' | 'bad_date'
  | 'draft_none_title' | 'draft_none_body' | 'draft_confirm_title'
  | 'draft_confirm_body' | 'draft_ref' | 'draft_restored'
  | 'print_incomplete' | 'print_draft_saved'

export type SectionKey =
  | 'quotation' | 'general' | 'production' | 'quality' | 'planning'
  | 'planning_tab' | 'source' | 'work_orders' | 'pricing' | 'history'
  | 'deduction_box' | 'apply_deduction_above'

export type ButtonKey =
  | 'new' | 'calculate' | 'save' | 'print' | 'variables' | 'reset_formula'
  | 'search' | 'clear_filters' | 'view_companies' | 'delete' | 'load' | 'restore'
  | 'sync' | 'server' | 'use_existing' | 'more_details' | 'hide_details'
  | 'attach' | 'qc_toggle'

export type TabKey = 'pricing' | 'planning' | 'drawing' | 'history'

export type PriceBoxKey =
  | 'calculated' | 'final_piece' | 'kg_when_selling_by_kg' | 'kg_when_selling_by_piece'

export type ChoiceKey = 'thickness_mode' | 'sale_basis' | 'sort'

export type FilterKey =
  | 'customer' | 'item' | 'product_key' | 'size' | 'date_from' | 'date_to'
  | 'sort' | 'all_types' | 'empty' | 'count'

export type Labels = {
  app_title: string
  app_subtitle: string
  header_subtitle: string
  tabs: Record<TabKey, string>
  buttons: Record<ButtonKey, string>
  steps: string
  fields: Record<FieldKey, string>
  sections: Record<SectionKey, string>
  /** The desktop's seven Section.TLabel background colours, by name. */
  section_colors: Record<string, string>
  choices: Record<ChoiceKey, { value: string; label: string }[]>
  price_boxes: Record<PriceBoxKey, string>
  /** What the green line beside the sale-basis box says before a calculation;
   *  after one, the server sends display.primary_line instead. */
  primary_hints: Record<'kg' | 'piece', string>
  notes: Record<NoteKey, string>
  results: { key: string; label: string; live_label?: string }[]
  planning: {
    find: string
    load: string
    summary_idle: string
    fields: Record<
      | 'production_width' | 'production_length' | 'production_thickness'
      | 'production_gusset' | 'packaging' | 'fixed_qty' | 'production_notes',
      string
    >
    compare: string
    compare_idle: string
    next_note: string
    messages: Record<
      | 'select_first' | 'not_found' | 'missing_source' | 'cannot_compare'
      | 'loaded' | 'missing_source_work_order' | 'prepared',
      string
    >
  }
  work_orders: {
    tabs: Record<'blown' | 'cutting', string>
    note: string
    copy: Record<'blown' | 'cutting', string>
    print: Record<'blown' | 'cutting', string>
    names: Record<'blown' | 'cutting', string>
  }
  history: {
    section: string
    buttons: Record<'details' | 'edit' | 'print_selected' | 'delete_selected' | 'related', string>
    edit_note: string
    select_first: string
    delete_confirm: string
    deleted_status: string
    deleted_body: string
    delete_missing: string
    details_title: string
    related_title: string
    related_info: string
    related_formula: string
    related_none: string
    edit_ref: string
    edit_status: string
    revised_from: string
    new_status: string
    view_table: string
    view_tree: string
    tree_hint: string
    tree_col_customer: string
    tree_col_code: string
    tree_col_products: string
    tree_col_quotes: string
    tree_col_period: string
    tree_col_product: string
    tree_col_size: string
    tree_col_unit: string
    tree_col_latest: string
    tree_col_range: string
    tree_empty: string
    tree_loading: string
  }
  history_columns: { key: string; label: string; width: number }[]
  related_columns: { key: string; label: string; width: number }[]
  history_filters: Record<FilterKey, string>
  /** The button that sends ticked prices to PacOs, and every sentence
   *  around it - the refusals included, in Thai and English both. */
  bridge: Record<
    | 'check_col'
    | 'button'
    | 'button_count'
    | 'select_first'
    | 'none'
    | 'mixed_customers'
    | 'no_customer_code'
    | 'too_many'
    | 'missing'
    | 'needs_pacos_login'
    | 'off'
    | 'sending'
    | 'sent',
    string
  >
  /** Which boxes each product draws. Served rather than held here so the list
   *  sits beside the calculator it mirrors - see api/screen.py. */
  fields_by_product: Record<string, string[]>
  asks_length_reference: string[]
  drawing: {
    tab: string
    status_idle: string
    buttons: Record<'copy' | 'preview' | 'save' | 'new' | 'search' | 'open', string>
    sections: Record<'document' | 'dimensions' | 'features' | 'register', string>
    fields: Record<
      | 'doc_no' | 'date' | 'revision' | 'customer_code' | 'customer' | 'title'
      | 'part_no' | 'material' | 'color' | 'printing' | 'product_type'
      | 'length_reference' | 'display_unit' | 'thickness_side'
      | 'width' | 'length' | 'height' | 'gusset'
      | 'tol_lo' | 'tol_hi' | 'tol_thickness'
      | 'holes_count' | 'holes_dia' | 'label_w' | 'label_h' | 'extra_notes',
      string
    >
    not_issued: string
    notes: Record<'revision' | 'thickness' | 'standard', string>
    register_columns: { key: string; label: string; width: number }[]
    statuses: Record<
      | 'copied' | 'previewed' | 'saved' | 'reset' | 'select_row' | 'opened'
      | 'cannot_build' | 'cannot_save',
      string
    >
    errors: Record<'need_customer' | 'need_title', string>
  }
  formulas: Record<'title' | 'weight' | 'price' | 'reset' | 'close' | 'variables', string>
}

export type Meta = {
  version: string
  /** What a PERSON is shown. `version` is a build string for a log. */
  version_label: string
  /** Whose password the gate asks for: this server's own table, or PacOs. */
  sign_in_with?: 'local' | 'pacos'
  /** Whether ticked prices can be sent to PacOs from the history tab. */
  pacos_bridge?: boolean
  products: Record<string, string>
  length_references: Record<string, string>
  dimension_units: string[]
  thickness_units: string[]
  default_weight_formulas: Record<string, string>
  default_price_formula: string
  formula_variables: Record<string, string>
  /** The Formula Variables window's whole text, composed on the server the
   *  way show_formula_help composes it. */
  formula_help_text: string
  labels: Labels
}

/** Open to anyone: the sign-in screen draws itself from these words, so it
 *  cannot be behind the sign-in. */
export const getMeta = () => request<Meta>('/api/meta')

export const getMe = () => request<User>('/api/me')

// --------------------------------------------------------- the calculations

/** Work the price out. The browser sends the QUESTION and prints the answer;
 *  it never does the arithmetic itself (LAW K1). */
export const calculate = (body: CalcRequest, signal?: AbortSignal) =>
  request<CalcResponse>('/api/calculate', {
    method: 'POST',
    body: JSON.stringify(body),
    ...(signal ? { signal } : {}),
  })

export type CoaSource = {
  quote_ref: string; customer: string; customer_code: string; part_no: string; product: string
  size_text: string; width_mm: number; length_mm: number; thickness_mm: number
  thickness_mode: 'side' | 'pair'; line: string
  special_requirements?: string
}
export type CoaRecord = Record<string, string | number | null> & { id: number; quote_ref: string; status: string }
export type CoaSave = {
  id?: number; status: string; quote_ref: string; po_no: string; lot_no: string
  production_date: string | null; inspection_date: string | null; issue_date: string | null
  quantity: string; material: string; color: string; printing: string
  width_tolerance_mm: number; length_tolerance_mm: number; thickness_tolerance_mm: number
  actual_width_mm: number | null; actual_length_mm: number | null; actual_thickness_mm: number | null
  result: string; remarks: string; checked_by: string; approved_by: string
}
export const coaSources = (q = '') => request<{ rows: CoaSource[] }>(`/api/coa/sources${tail({ q })}`)
export const listCoas = () => request<{ rows: CoaRecord[] }>('/api/coa')
export const saveCoa = (body: CoaSave) => request<{ row: CoaRecord }>('/api/coa', { method: 'POST', body: JSON.stringify(body) })
export const coaPrintHtml = (id: number) => request<{ html: string }>(`/api/coa/${id}/print`)

export type SampleSource = CoaSource & { quote_version?:number; product_key:string; gusset_mm:number; tolerance_width_mm:number; tolerance_length_mm:number; tolerance_thickness_mm:number;
  tolerance_gusset_left_mm?:number; tolerance_gusset_right_mm?:number;
  width_original?:{value:number;unit:string}; length_original?:{value:number;unit:string}; gusset_original?:{value:number;unit:string}; thickness_original?:{value:number;unit:string} }
export type SampleMeasurement = { width:number|null; length:number|null; thickness:number|null; gusset_left:number|null; gusset_right:number|null }
export type LengthDatum = 'opening_to_bottom' | 'opening_to_seal' | null
export type SampleInspectionSave = { id?:number; expected_revision?:number; expected_quote_version?:number; request_id?:string; length_datum:LengthDatum; quote_ref:string; inspection_date:string; tolerance_width_mm:number; tolerance_length_mm:number;
  tolerance_thickness_mm:number; tolerance_gusset_left_mm:number; tolerance_gusset_right_mm:number; measurements:SampleMeasurement[];
  remarks:string; checked_by:string; approved_by:string }
export type SampleInspectionRecord = Omit<SampleInspectionSave, 'measurements'> & { id:number; report_no:string; customer:string; product:string; overall_result:string; results_json:SampleMeasurement[]; source_snapshot:SampleSource; revision:number }
export const sampleSources = (q='') => request<{rows:SampleSource[]}>(`/api/sample-inspections/sources${tail({q})}`)
export const listSampleInspections = () => request<{rows:SampleInspectionRecord[]}>('/api/sample-inspections')
export const saveSampleInspection = (body:SampleInspectionSave) => request<{row:SampleInspectionRecord}>('/api/sample-inspections',{method:'POST',body:JSON.stringify(body)})
export const deleteSampleInspection = (id:number) => request<{deleted:number}>(`/api/sample-inspections/${id}`,{method:'DELETE'})
export const samplePrintHtml = (id:number) => request<{html:string}>(`/api/sample-inspections/${id}/print`)

export type SearchParams = {
  customer?: string
  item?: string
  product_key?: string
  size?: string
  date_from?: string
  date_to?: string
  sort?: string
  limit?: number
}

export const searchQuotations = (params: SearchParams, signal?: AbortSignal) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const tail = query.toString()
  return request<{ rows: QuoteRow[]; count: number }>(
    `/api/quotations${tail ? `?${tail}` : ''}`,
    signal ? { signal } : {},
  )
}

/** The history table's own rows: fifteen cells per row, already formatted the
 *  desktop's way on the server, plus the count line. */
export const historySearch = (params: SearchParams, signal?: AbortSignal) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const tail = query.toString()
  return request<{ rows: Record<string, string>[]; count_text: string }>(
    `/api/history${tail ? `?${tail}` : ''}`,
    signal ? { signal } : {},
  )
}

/* THE BOOK AS FOLDERS - three levels, each fetched when its folder opens. */
export type TreeCustomer = {
  customer: string
  customer_code: string
  quotes: number
  products: number
  period: string
}
export type TreeProduct = {
  product_name: string
  size: string
  quotes: number
  period: string
  latest_price: string
  price_range: string
  sale_unit: string
}

function tail(params: Record<string, string | number | undefined>): string {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') query.set(key, String(value))
  }
  const text = query.toString()
  return text ? `?${text}` : ''
}

const treeFilters = (p: SearchParams) => ({
  customer: p.customer, item: p.item, product_key: p.product_key, size: p.size,
  date_from: p.date_from, date_to: p.date_to,
})

export const historyTreeCustomers = (params: SearchParams, signal?: AbortSignal) =>
  request<{ groups: TreeCustomer[]; count_text: string }>(
    `/api/history/tree/customers${tail(treeFilters(params))}`,
    signal ? { signal } : {},
  )

export const historyTreeProducts = (exactCustomer: string, params: SearchParams, signal?: AbortSignal) =>
  request<{ groups: TreeProduct[] }>(
    `/api/history/tree/products${tail({ ...treeFilters(params), exact_customer: exactCustomer })}`,
    signal ? { signal } : {},
  )

export const historyTreeRows = (
  exactCustomer: string,
  productName: string,
  sizeText: string,
  params: SearchParams,
  signal?: AbortSignal,
) =>
  request<{ rows: Record<string, string>[] }>(
    `/api/history/tree/rows${tail({
      ...treeFilters(params),
      exact_customer: exactCustomer,
      product_name: productName,
      size_text: sizeText,
    })}`,
    signal ? { signal } : {},
  )

/** The Details window's text, line for line. */
export const quotationDetails = (quoteRef: string) =>
  request<{ title: string; text: string }>(
    `/api/quotations/${encodeURIComponent(quoteRef)}/details`,
  )

/** The Related Companies window: thirteen formatted cells per row. */
export const relatedTable = (params: {
  product_reference?: string
  item_description?: string
  size_text?: string
}) => {
  const query = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value) query.set(key, value)
  }
  return request<{ title: string; rows: Record<string, string>[]; count: number }>(
    `/api/related/table?${query.toString()}`,
  )
}

/** Everything the Edit button pours back into the form, as box-ready strings. */
export const quotationForm = (quoteRef: string) =>
  request<{ quote_ref: string; version: number; form: Record<string, unknown>; ref_text: string; status: string;
    calculator_compatible?: boolean; calculator_warning?: string }>(
    `/api/quotations/${encodeURIComponent(quoteRef)}/form`,
  )

export const deleteQuotation = async (quoteRef: string, reason: string, actor: string) => {
  const capability = await quotationTrash()
  if (capability.reason_required !== true) throw new Error('บริการยังเป็นรุ่นเดิม กรุณาเริ่มบริการโปรแกรมใหม่ก่อนลบ เพื่อบันทึกเหตุผลให้ครบถ้วน')
  return request<{ deleted: string }>(`/api/quotations/${encodeURIComponent(quoteRef)}`, {
    method: 'DELETE',
    body: JSON.stringify({ reason, actor }),
  })
}

export type TrashRow = { ref: string; reason: string; actor: string; time: string }
export const quotationTrash = () => request<{ rows: TrashRow[]; reason_required?: boolean }>('/api/history/trash')
export const restoreQuotation = (ref: string) => request<{ restored: string }>(
  `/api/quotations/${encodeURIComponent(ref)}/restore`, { method: 'POST' })

/** The approval drawing, as SVG, drawn by the desktop program's own
 *  drawing.py on the server. */
export const drawApproval = (body: DrawingRequest) =>
  request<{ svg: string }>('/api/drawing', { method: 'POST', body: JSON.stringify(body) })

/** The printable A4-landscape page the desktop's Preview & Print opens. */
export const drawingHtml = (body: DrawingRequest) =>
  request<{ html: string }>('/api/drawing/html', { method: 'POST', body: JSON.stringify(body) })

export type DrawingSave = {
  doc_no: string
  quote_ref: string
  drawing_date: string
  revision: string
  customer: string
  customer_code: string
  title: string
  part_no: string
  product_key: string
  length_datum: string
  display_unit: 'mm' | 'inch'
  width: { value: number; unit: string }
  length: { value: number; unit: string }
  height: { value: number; unit: string }
  gusset: { value: number; unit: string }
  thickness: { value: number; unit: string; mode: 'side' | 'pair' }
  material: string
  color: string
  printing: string
  tol_dim_lo: number
  tol_dim_hi: number
  tol_thickness: number
  holes_count: number
  holes_dia: string
  label_w: number
  label_h: number
  extra_notes: string[]
}

/** Save into the register. An empty doc_no is issued a DFA- number by one SQL
 *  statement; a row that carries one keeps it - a revision is not a new
 *  document. */
export const saveDrawing = (body: DrawingSave) =>
  request<{ doc_no: string; status: string }>('/api/drawings', {
    method: 'POST',
    body: JSON.stringify(body),
  })

export const drawingRegister = (q: string) =>
  request<{ rows: Record<string, string>[] }>(`/api/drawings?q=${encodeURIComponent(q)}`)

export const getDrawing = (docNo: string) =>
  request<{ doc_no: string; form: Record<string, string> }>(
    `/api/drawings/${encodeURIComponent(docNo)}`,
  )

export type Customer = { customer: string; customer_code: string; times: number }

/** Who has been quoted before, the most-quoted first. Read once and kept:
 *  627 names is nothing to filter in memory and everything to re-query
 *  seventeen thousand rows for while somebody is typing. */
export const getCustomers = () => request<{ rows: Customer[] }>('/api/customers')

/** Send the ticked rows to PacOs as ONE handoff. The answer carries the
 *  PacOs address to open; a refusal carries the server's own bilingual
 *  sentence (rows of two customers, a row with no PacOs customer). */
export const pushToPacos = (refs: string[]) =>
  request<{ handoff_id: string; url: string; lines: number; customer: string }>('/api/bridge/handoffs', {
    method: 'POST',
    body: JSON.stringify({ refs }),
  })

// ------------------------------------------------------------- the planning

export type SourceRow = { quote_ref: string; line: string }

/** The planning tab's source picker: one typed string matched against the
 *  reference, the customer and the item, newest first. */
export const planningSources = (q: string, signal?: AbortSignal) =>
  request<{ rows: SourceRow[] }>(
    `/api/planning/sources?q=${encodeURIComponent(q)}`,
    signal ? { signal } : {},
  )

export type SourcePrefill = {
  quote_ref: string
  line: string
  width: string
  length: string
  thickness: string
  gusset: string
  package: string
  quantity: string
  summary: string
  status: string
  product_key: string
  sack_quantity: string
  sack_weight_kg: string
  grams_per_item: string
  items_per_kg: string
  adjusted_items: string
  tolerance_width_mm: string
  tolerance_length_mm: string
  tolerance_thickness_mm: string
  tolerance_gusset_left_mm: string
  tolerance_gusset_right_mm: string
  drawing_doc_no: string
  special_features: string
  sales_product: string
  sales_part_no: string
  sales_size: string
  sales_width: string
  sales_length: string
  sales_thickness: string
  sales_thickness_mode: string
  sale_basis: 'piece' | 'kg'
  small_pack_quantity: string
  package_count_per_sack: string
}

/** Resolve one picked/typed/pasted line into the planning prefill - the
 *  strings arrive already formatted the desktop's way. */
export const planningSource = (selected: string) =>
  request<SourcePrefill>(`/api/planning/source?selected=${encodeURIComponent(selected)}`)

/** The weight comparison. The ratio is worked out on the server, from the
 *  desktop's own sum - the browser only prints the sentence (LAW P1). */
export const planningCompare = (body: {
  quote_ref: string
  quantity: string
  width: string
  length: string
  thickness: string
  gusset: string
  sack_quantity: string
}) =>
  request<{ line: string; grams_per_item: string; items_per_kg: string; adjusted_items: string; sack_weight_kg: string }>('/api/planning/compare', {
    method: 'POST',
    body: JSON.stringify(body),
  })

/** The shop-floor sheet, as the finished HTML page the desktop writes. */
export const workOrderHtml = (body: {
  department: 'blown' | 'cutting'
  source: string
  product_type: string
  width: string
  length: string
  thickness: string
  gusset: string
  package: string
  notes: string
  drawing_doc_no: string
  special_features: string
  sack_quantity: string
  sack_weight: string
  tolerance_width: string
  tolerance_length: string
  tolerance_thickness: string
  tolerance_gusset_left: string
  tolerance_gusset_right: string
  grams_per_item: string
  items_per_kg: string
  adjusted_items: string
  sale_basis: 'piece' | 'kg'
  package_style: string
  small_pack_quantity: string
  package_count_per_sack: string
  total_package_quantity: string
  small_pack_weight: string
  width_limits: string
  length_limits: string
  thickness_limits: string
  gusset_limits: string
  standard_sack_weight: string
  maximum_sack_weight: string
  comparison_quantity_pcs: string
  quoted_same_quantity_weight: string
  production_same_quantity_weight: string
  acceptable_same_quantity_weight: string
  same_quantity_weight_difference: string
  customer_spec_thickness: string
  production_order_thickness: string
}) =>
  request<{ html: string }>('/api/work-orders/html', {
    method: 'POST',
    body: JSON.stringify(body),
  })

/** The A4 print summary, built by the server from the same request the
 *  calculation uses - same figures, same Thai, same auto window.print(). */
export const printHtml = (body: {
  moq_quantity?: string
  moq_unit?: string
  calc: CalcRequest
  quote_date: string
  customer: string
  customer_code: string
  item_description: string
  product_reference: string
  quote_ref: string
  /** The desktop's "แก้ไขจาก / Revised From" identity row, when editing. */
  revised_from_ref: string
}) => request<{ html: string }>('/api/print/html', { method: 'POST', body: JSON.stringify(body) })

/** Reprint a saved record from its stored inputs. */
export const printSaved = (quoteRef: string) =>
  request<{ html: string }>(`/api/quotations/${encodeURIComponent(quoteRef)}/print`)

/** Keep it. The server works the figures out AGAIN from the same request and
 *  stores what IT got, so what ends up under somebody's name is a number this
 *  system produced rather than one the browser sent up (LAW K1). */
export const saveQuotation = (body: {
  moq_quantity?: string
  moq_unit?: string
  calc: CalcRequest
  quote_date: string
  customer: string
  customer_code: string
  item_description: string
  product_reference: string
  /** Set when the form was loaded from a saved record: the desktop's
   *  edit-as-revision link, never an overwrite. */
  revised_from_ref?: string
  update_ref?: string
  expected_version?: number
  request_id?: string
}) =>
  request<{ quote_ref: string; id: number; created_at: string; version: number }>('/api/quotations', {
    method: 'POST',
    body: JSON.stringify(body),
  })
