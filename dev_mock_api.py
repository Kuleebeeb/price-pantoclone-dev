"""Local visual-review API with a small persistent store for TEST revisions."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse
import json, os, re, sqlite3, sys, time, threading

ROOT=Path(__file__).parent
HISTORY_DB=ROOT/'local-data'/'pantongone-history.sqlite3'
SAVED_FILE=ROOT/'local-data'/'visual-review-saved.json'
SAVED_LOCK=threading.Lock()
sys.path.insert(0,str(ROOT/'server'/'core'))
from calculator import *
from drawing import DrawingSpec, PRODUCT_TO_SHAPE, render_svg, render_html

META=json.loads((ROOT/'pantongone-frontend'/'src'/'test-fixtures'/'meta.json').read_text(encoding='utf-8'))
META['default_weight_formulas']=DEFAULT_WEIGHT_FORMULAS
META['default_price_formula']=DEFAULT_PRICE_FORMULA
DEMO_LINE='QT-20260830-0001 | CSK | CSK Plasatic Co.,Ltd | PE BAG 4 x 12 inch'
DEMO_FORM={'customer':'CSK Plasatic Co.,Ltd','customer_code':'CSK','quote_date':'2026-08-30','item_description':'PE BAG 4 x 12 inch','product_reference':'4P677198-1','product_key':'flat','width':'4','width_unit':'นิ้ว','length':'12','length_unit':'นิ้ว','height':'','gusset':'','thickness':'0.16','thickness_unit':'มม.','thickness_mode':'pair','length_reference':'ปากถึงก้นถุง / Opening to Bottom','tolerance_width':'10','tolerance_length':'10','tolerance_thickness':'0.01','tolerance_gusset_left':'','tolerance_gusset_right':'','special_requirements':'ซีลก้นตรงและแข็งแรง\nปากถุงเปิดง่าย\nห้ามมีรอยย่น รอยขาด หรือสิ่งปนเปื้อน'}

UNIT_TO_UI={'inch':'นิ้ว','in':'นิ้ว','นิ้ว':'นิ้ว','cm':'ซม.','ซม.':'ซม.','mm':'มม.','มม.':'มม.','m':'เมตร','meter':'เมตร','เมตร':'เมตร'}
PRODUCT_MAP={'flat':'flat','bag':'flat','sleeve':'sleeve','open_ended_sleeve':'sleeve','gusset':'gusset','sheet':'opaque','opaque':'opaque','roll':'roll','cover':'cover'}

def legacy_rows(include_cancelled=False):
    if not HISTORY_DB.exists(): return []
    con=sqlite3.connect(HISTORY_DB)
    con.row_factory=sqlite3.Row
    sql='''select r.*, q.document_no, c.cancelled_at
           from records r left join quote_series q on q.quote_no=r.quote_no
           left join cancellation c on c.record_id=r.id'''
    if not include_cancelled: sql+=' where c.record_id is null'
    sql+=' order by r.id desc'
    rows=[]
    for row in con.execute(sql):
        item=dict(row)
        try: item['data_json']=json.loads(item.get('data') or '{}')
        except Exception: item['data_json']={}
        try: item['result_json']=json.loads(item.get('result') or '{}')
        except Exception: item['result_json']={}
        rows.append(item)
    con.close()
    return rows

def legacy_ref(row):
    base=row.get('document_no') or f"TEST #{row.get('quote_no') or row['id']}"
    rev=int(row.get('revision') or 0)
    return f'{base} / Revise Price {rev:02d}' if rev else base

def legacy_product(value): return PRODUCT_MAP.get(str(value or 'flat').strip().lower(),'flat')
def ui_unit(value,default='ซม.'): return UNIT_TO_UI.get(str(value or '').strip().lower(),default)
def text_num(value): return '' if value is None else str(value)
def as_float(value,default=0.0):
    try: return float(value or 0)
    except Exception: return default

def to_mm_value(value,unit):
    n=as_float(value)
    u=str(unit or '').strip().lower()
    if u in {'inch','in','นิ้ว'}: return n*25.4
    if u in {'cm','ซม.'}: return n*10
    if u in {'m','meter','เมตร'}: return n*1000
    return n

def thickness_mm_value(value,unit):
    n=as_float(value)
    return n/1000 if str(unit or '').strip().lower() in {'micron','ไมครอน','um','µm'} else n

def legacy_tolerance(value, standard):
    """Old quotations predate tolerance fields; retain entered values and use the approved workshop standard only when blank."""
    return as_float(value) if str(value or '').strip() else standard

def legacy_form(row):
    d=row['data_json']; r=row['result_json']
    sale=str(d.get('sale') or d.get('sale_basis') or 'kg').lower()
    return {
      'customer':text_num(d.get('customer')),'customer_code':text_num(d.get('customer_code')),
      'quote_date':text_num(d.get('quote_date') or row.get('date')),
      'item_description':text_num(d.get('item')),'product_reference':text_num(d.get('item_code')),
      'product_key':legacy_product(d.get('product')),'width':text_num(d.get('width')),
      'width_unit':ui_unit(d.get('width_unit')),'length':text_num(d.get('length')),
      'length_unit':ui_unit(d.get('length_unit')),'height':text_num(d.get('height')),
      'gusset':text_num(d.get('gusset')),'sold_length':text_num(d.get('meters') or d.get('sold_length')),
      'sold_length_unit':ui_unit(d.get('sold_length_unit'),'เมตร'),'thickness':text_num(d.get('thickness')),
      'thickness_unit':ui_unit(d.get('thickness_unit'),'มม.'),'thickness_mode':'side' if str(d.get('basis')).lower()=='side' else 'pair',
      'bottom_allowance':text_num(d.get('allowance')),'length_reference':text_num(d.get('length_reference') or 'ปากถึงก้นถุง / Opening to Bottom'),
      'density':text_num(d.get('density') or '0.92'),'material_price':text_num(d.get('material')),
      'deduction':text_num(d.get('deduction') or d.get('deduction_percent') or '10'),'apply_deduction':as_float(d.get('deduction') or 10)>0,
      'sale_basis':'piece' if sale in {'piece','pc','pcs','ใบ'} else 'kg','price_per_kg':text_num(d.get('pricekg') or r.get('finalkg')),
      'price_per_piece':text_num(d.get('final') or r.get('finalpiece')),'order_quantity':text_num(d.get('qty')),
      'pack_quantity':text_num(d.get('pack')),'sack_quantity':text_num(d.get('sack')),
      'control_min':text_num(d.get('control_min')),'control_max':text_num(d.get('control_max')),
      'roof_gsm':text_num(d.get('roof_gsm') or '120'),'mesh_gsm':text_num(d.get('mesh_gsm') or '80'),
      'weight_formula':text_num(d.get('weight_formula')),'price_formula':text_num(d.get('price_formula')),
      'tolerance_width':text_num(d.get('tolerance_width')),'tolerance_length':text_num(d.get('tolerance_length')),
      'tolerance_thickness':text_num(d.get('tolerance_thickness')),'tolerance_gusset_left':text_num(d.get('tolerance_gusset_left')),
      'tolerance_gusset_right':text_num(d.get('tolerance_gusset_right')),'special_requirements':text_num(d.get('special_requirements'))}

def legacy_source(row):
    d=row['data_json']; f=legacy_form(row); ref=legacy_ref(row)
    width=to_mm_value(d.get('width'),d.get('width_unit')); length=to_mm_value(d.get('length'),d.get('length_unit'))
    gusset=to_mm_value(d.get('gusset'),d.get('width_unit')); th=thickness_mm_value(d.get('thickness'),d.get('thickness_unit'))
    product=f['item_description'] or f['product_reference'] or 'สินค้าเดิม'
    thickness_mode=f['thickness_mode']; thickness_original=as_float(f['thickness'])
    side_match=re.search(r'(\d+(?:\.\d+)?)\s*(?:mm\.?)?\s*/\s*side', product, re.IGNORECASE)
    if side_match:
        thickness_original=float(side_match.group(1)); th=thickness_original; thickness_mode='side'
    line=' | '.join(x for x in [ref,f['customer_code'],f['customer'],product] if x)
    return {'quote_ref':ref,'line':line,'customer':f['customer'],'customer_code':f['customer_code'],'part_no':f['product_reference'],
      'product':product,'size_text':f"{f['width']} x {f['length']} {f['width_unit']}",'width_mm':width,'length_mm':length,
      'thickness_mm':th,'thickness_mode':thickness_mode,'product_key':f['product_key'],'gusset_mm':gusset,
      'tolerance_width_mm':legacy_tolerance(f['tolerance_width'],10),'tolerance_length_mm':legacy_tolerance(f['tolerance_length'],10),
      'tolerance_thickness_mm':legacy_tolerance(f['tolerance_thickness'],0.01),'tolerance_gusset_left_mm':legacy_tolerance(f['tolerance_gusset_left'],10),
      'tolerance_gusset_right_mm':legacy_tolerance(f['tolerance_gusset_right'],10),'special_requirements':f['special_requirements'],
      'width_original':{'value':as_float(f['width']),'unit':f['width_unit']},'length_original':{'value':as_float(f['length']),'unit':f['length_unit']},
      'gusset_original':{'value':as_float(f['gusset']),'unit':f['width_unit']},'thickness_original':{'value':thickness_original,'unit':f['thickness_unit']}}

def history_piece_price(grams, basis, form):
    # Derived display only. Never replace the recorded selling price.
    grams=as_float(grams); basis=as_float(basis)
    deduction=as_float(form.get('deduction')) if form.get('sale_basis')=='piece' and form.get('apply_deduction') else 0
    if grams<=0 or basis<=0 or not 0<=deduction<100: return ''
    return str(basis / ((1000/grams)*(1-deduction/100)))

def legacy_history(row):
    f=legacy_form(row); r=row['result_json']; src=legacy_source(row)
    grams=as_float(r.get('kg'))*1000
    if not grams: grams=as_float(r.get('grams_per_item'))
    return {'_product_key':f['product_key'],'ref':legacy_ref(row),'date':f['quote_date'],'customer_code':f['customer_code'],'customer':f['customer'],
      'sale_unit':'ใบ / piece' if f['sale_basis']=='piece' else 'กก. / kg','item':f['item_description'],'product':f['product_reference'],
      'size':src['size_text'],'thickness':f"{f['thickness']} {f['thickness_unit']}/{'side' if f['thickness_mode']=='side' else 'pair'}",
      'grams':f'{grams:.3f}' if grams else '','price_basis':f['price_per_kg'],'calc_price':history_piece_price(grams,r.get('finalkg') or f['price_per_kg'],f),
      'price_kg':text_num(r.get('finalkg') or f['price_per_kg']),'price':text_num(r.get('finalpiece') or f['price_per_piece']),
      'pack':text_num(r.get('packkg') or f['pack_quantity'])}

def find_legacy(ref):
    wanted=unquote(ref)
    return next((r for r in legacy_rows(True) if legacy_ref(r)==wanted),None)

def measure(x): return to_cm(float(x.get('value',0) or 0),x.get('unit','ซม.'))
def mm(x): return measure(x)*10
def thick(x): return thickness_to_mm(float(x.get('value',0) or 0),x.get('unit','มม.'))
def fmt(v,d=3): return f'{v:,.{d}f}'

def saved_rows():
    if not SAVED_FILE.exists(): return []
    try: return json.loads(SAVED_FILE.read_text(encoding='utf-8'))
    except Exception: return []

def write_saved(rows):
    SAVED_FILE.parent.mkdir(parents=True,exist_ok=True)
    temp=SAVED_FILE.with_suffix('.tmp')
    temp.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(SAVED_FILE)

def saved_ref(body, rows):
    revised=str(body.get('revised_from_ref') or '').strip()
    if revised:
        base=re.sub(r'\s*/\s*Revise Price\s+\d+$','',revised,flags=re.I)
        refs=[str(x.get('quote_ref') or '') for x in rows]+[legacy_ref(x) for x in legacy_rows(True)]
        revisions=[int(m.group(1)) for ref in refs if ref==base or ref.startswith(base+' / Revise Price')
                   for m in [re.search(r'Revise Price\s+(\d+)$',ref,re.I)] if m]
        return f'{base} / Revise Price {(max(revisions,default=0)+1):02d}'
    day=re.sub(r'\D','',str(body.get('quote_date') or time.strftime('%Y-%m-%d')))
    prefix=f'LOCAL-QT-{day}-'
    number=1+sum(1 for x in rows if str(x.get('quote_ref') or '').startswith(prefix))
    return f'{prefix}{number:04d}'

def saved_form(row):
    body=row.get('body') or {}; c=body.get('calc') or {}
    def field(name,part='value',default=''):
        value=c.get(name,default)
        return value.get(part,default) if isinstance(value,dict) else value
    return {'customer':body.get('customer',''),'customer_code':body.get('customer_code',''),'quote_date':body.get('quote_date',''),
      'item_description':body.get('item_description',''),'product_reference':body.get('product_reference',''),'product_key':c.get('product_key','flat'),
      'width':text_num(field('width')),'width_unit':text_num(field('width','unit','ซม.')),'length':text_num(field('length')),
      'length_unit':text_num(field('length','unit','ซม.')),'height':text_num(field('height')),'gusset':text_num(field('gusset')),
      'sold_length':text_num(field('sold_length')),'sold_length_unit':text_num(field('sold_length','unit','เมตร')),
      'thickness':text_num(field('thickness')),'thickness_unit':text_num(field('thickness','unit','มม.')),
      'thickness_mode':text_num(field('thickness','mode','pair')),'bottom_allowance':text_num(field('bottom_allowance')),
      'length_reference':text_num(c.get('length_reference')),'density':text_num(c.get('density_g_cm3')),
      'material_price':text_num(c.get('material_price_per_kg')),'deduction':text_num(c.get('deduction_percent')),
      'apply_deduction':bool(c.get('apply_deduction',True)),'sale_basis':text_num(c.get('sale_basis') or 'kg'),
      'price_per_kg':text_num(c.get('selling_price_per_kg_override')),'price_per_piece':text_num(c.get('selling_price_per_piece_override')),
      'order_quantity':text_num(c.get('order_quantity')),'pack_quantity':text_num(c.get('pack_quantity')),
      'sack_quantity':text_num(c.get('sack_quantity')),'control_min':text_num(c.get('control_min_g')),'control_max':text_num(c.get('control_max_g')),
      'roof_gsm':text_num(c.get('roof_gsm')),'mesh_gsm':text_num(c.get('mesh_gsm')),'weight_formula':text_num(c.get('weight_formula')),
      'price_formula':text_num(c.get('price_formula')),'tolerance_width':text_num(field('tolerance_width')),
      'tolerance_length':text_num(field('tolerance_length')),'tolerance_thickness':text_num(field('tolerance_thickness')),
      'tolerance_gusset_left':text_num(field('tolerance_gusset_left')),'tolerance_gusset_right':text_num(field('tolerance_gusset_right')),
      'special_requirements':text_num(c.get('special_requirements'))}

def saved_history(row):
    body=row.get('body') or {}; c=body.get('calc') or {}; f=saved_form(row); result=calc(c)
    v=result.get('results') or {}; display=result.get('display') or {}
    width=c.get('width') or {}; length=c.get('length') or {}; thickness=c.get('thickness') or {}
    size=f"{width.get('value','')} x {length.get('value','')} {width.get('unit','')}"
    return {'_product_key':f['product_key'],'ref':row.get('quote_ref',''),'date':body.get('quote_date',''),'customer_code':body.get('customer_code',''),
      'customer':body.get('customer',''),'sale_unit':'ใบ / piece' if c.get('sale_basis')=='piece' else 'กก. / kg',
      'item':body.get('item_description',''),'product':body.get('product_reference',''),'size':size,
      'thickness':f"{thickness.get('value','')} {thickness.get('unit','')}/{thickness.get('mode','pair')}",
      'grams':text_num(v.get('grams_per_item') or str(display.get('grams','')).split(' ')[0]),'price_basis':text_num(c.get('selling_price_per_kg_override')),
      'calc_price':history_piece_price(v.get('grams_per_item'),c.get('selling_price_per_kg_override'),f),'price_kg':text_num(c.get('selling_price_per_kg_override')),
      'price':text_num(c.get('selling_price_per_piece_override')),'pack':text_num(v.get('pack_weight_kg'))}

def saved_source(row):
    body=row.get('body') or {}; c=body.get('calc') or {}; f=saved_form(row); ref=row.get('quote_ref','')
    width=c.get('width') or {}; length=c.get('length') or {}; gusset=c.get('gusset') or {}; thickness=c.get('thickness') or {}
    product=body.get('item_description') or body.get('product_reference') or 'สินค้าแก้ไข'
    thickness_value=as_float(thickness.get('value')); thickness_mode=str(thickness.get('mode') or 'pair')
    side_match=re.search(r'(\d+(?:\.\d+)?)\s*(?:mm\.?)?\s*/\s*side',product,re.I)
    if side_match: thickness_value=float(side_match.group(1)); thickness_mode='side'
    def tolerance(name,default):
        value=c.get(name) or {}; number=as_float(value.get('value') if isinstance(value,dict) else value)
        return number if number>0 else default
    line=' | '.join(x for x in [ref,body.get('customer_code',''),body.get('customer',''),product] if x)
    return {'quote_ref':ref,'line':line,'customer':body.get('customer',''),'customer_code':body.get('customer_code',''),
      'part_no':body.get('product_reference',''),'product':product,
      'size_text':f"{width.get('value','')} x {length.get('value','')} {width.get('unit','')}",
      'width_mm':to_mm_value(width.get('value'),width.get('unit')),'length_mm':to_mm_value(length.get('value'),length.get('unit')),
      'thickness_mm':thickness_value,'thickness_mode':thickness_mode,'product_key':c.get('product_key','flat'),
      'gusset_mm':to_mm_value(gusset.get('value'),gusset.get('unit')),
      'tolerance_width_mm':tolerance('tolerance_width',10),'tolerance_length_mm':tolerance('tolerance_length',10),
      'tolerance_thickness_mm':tolerance('tolerance_thickness',0.01),
      'tolerance_gusset_left_mm':tolerance('tolerance_gusset_left',10),'tolerance_gusset_right_mm':tolerance('tolerance_gusset_right',10),
      'special_requirements':c.get('special_requirements',''),
      'width_original':{'value':as_float(width.get('value')),'unit':width.get('unit','มม.')},
      'length_original':{'value':as_float(length.get('value')),'unit':length.get('unit','มม.')},
      'gusset_original':{'value':as_float(gusset.get('value')),'unit':gusset.get('unit','มม.')},
      'thickness_original':{'value':thickness_value,'unit':thickness.get('unit','มม.')}}

def find_saved(ref):
    wanted=unquote(ref)
    return next((row for row in saved_rows() if row.get('quote_ref')==wanted),None)

def calc(body):
    key=body.get('product_key','flat'); width=measure(body.get('width',{})); length=measure(body.get('length',{})); gusset=measure(body.get('gusset',{})); height=measure(body.get('height',{})); sold=measure(body.get('sold_length',{}))/100
    allowance=measure(body.get('bottom_allowance',{})) if key in {'flat','gusset'} else 0
    ti=thick(body.get('thickness',{})); mode=body.get('thickness',{}).get('mode','pair')
    material=float(body.get('material_price_per_kg',65)); basis=float(body.get('selling_price_per_kg_override',0)); markup=((basis/material)-1)*100 if material and basis else 0
    formula=body.get('weight_formula') or DEFAULT_WEIGHT_FORMULAS[key]
    pe_cover = key == 'cover' and formula == '(roof_area_cm2 + mesh_area_cm2) / (2.54 * 2.54) * thickness_side_mm / 1800 * 1000'
    if pe_cover:
        if ti <= 0: raise ValueError('Product Cover: กรุณากรอกความหนาต่อด้านให้มากกว่า 0')
        if mode != 'side': raise ValueError('Product Cover PE ใช้ความหนาต่อด้านเท่านั้น')
        if body.get('sale_basis') == 'piece' and (not body.get('apply_deduction') or float(body.get('deduction_percent',0)) != 10):
            raise ValueError('Product Cover ขายเป็นใบต้องหักจำนวนสำหรับคิดราคา 10%')
    r=calculate(product_key=key,width_cm=width,length_cm=length,height_cm=height,gusset_cm=gusset,sold_length_m=sold,bottom_allowance_cm=allowance,thickness_input_mm=ti,thickness_mode=mode,density_g_cm3=float(body.get('density_g_cm3',.92)),roof_gsm=float(body.get('roof_gsm',120)),mesh_gsm=float(body.get('mesh_gsm',80)),material_price_per_kg=material,markup_percent=markup,deduction_percent=float(body.get('deduction_percent',10)),pack_quantity=float(body.get('pack_quantity',0)),sack_quantity=float(body.get('sack_quantity',0)),apply_deduction=bool(body.get('apply_deduction',True)),sell_by_kg=body.get('sale_basis','kg')=='kg',selling_price_per_piece_override=float(body.get('selling_price_per_piece_override',0)),selling_price_per_kg_override=basis,order_quantity=float(body.get('order_quantity',1000)),control_min_g=float(body.get('control_min_g',0)),control_max_g=float(body.get('control_max_g',0)),weight_formula=formula,price_formula=body.get('price_formula') or DEFAULT_PRICE_FORMULA)
    display={'grams':fmt(r.grams_per_item)+' กรัม','items_per_kg':fmt(r.items_per_kg,2)+' ชิ้น','adjusted_items':fmt(r.production_items_per_kg,2)+' ชิ้น','calculated_piece':fmt(r.calculated_price_per_piece_from_kg)+' บาท/ชิ้น','primary_line':f'น้ำหนัก {fmt(r.grams_per_item)} g • {fmt(r.items_per_kg,2)} ชิ้น/กก.','derivation':'','size_text':f'{width:g} × {length:g} cm','deduction_caption':'หลังหักเผื่อผลิต','roof_area':'','mesh_area':''}
    # Round presentation only; r and its calculation variables retain full precision.
    display['grams']=fmt(r.grams_per_item,2)+' กรัม'
    display['calculated_piece']=fmt(r.calculated_price_per_piece_from_kg,2)+' บาท/ชิ้น'
    display['primary_line']=f'น้ำหนัก {fmt(r.grams_per_item,2)} g • {fmt(r.items_per_kg,2)} ชิ้น/กก.'
    display['pack_weight']=fmt(r.pack_weight_kg,2)+' กก.'
    display['sack_weight']=fmt(r.sack_weight_kg,2)+' กก.'
    display['derivation']=(f'ราคา/ใบ = ราคาขายต่อ กก. {fmt(basis,2)} ÷ จำนวนที่ใช้คิดราคา {fmt(r.production_items_per_kg,2)} ใบ/กก. ≈ {fmt(r.calculated_price_per_piece_from_kg,2)} บาท/ใบ'
                           if basis > 0 else 'กรอกราคาขายต่อ กก. เพื่อคำนวณราคา/ใบ')
    return {'results':r.variables,'normalized':{'width_cm':width,'length_cm':length,'gusset_cm':gusset,'thickness_input_mm':ti},'display':display,'human_summary':f'Weight {fmt(r.grams_per_item,2)} g/pc • Theoretical {fmt(r.items_per_kg,2)} pcs/kg • Adjusted {fmt(r.production_items_per_kg,2)} pcs/kg • แสดงผล 2 ตำแหน่ง คำนวณจากค่าเต็ม','price_basis':'DEMO','formulas':{'weight':formula,'price':body.get('price_formula') or DEFAULT_PRICE_FORMULA}}

def drawing(body):
    t=body.get('thickness',{})
    spec=DrawingSpec(doc_no=body.get('doc_no') or 'DEMO-DWG-001',customer=body.get('customer',''),title=body.get('title','') or body.get('product','SAMPLE DRAWING'),shape=PRODUCT_TO_SHAPE[body.get('product_key','flat')],revision=body.get('revision','A'),date=body.get('date',''),part_no=body.get('part_no','-'),customer_code=body.get('customer_code',''),material=body.get('material','POLYETHYLENE'),color=body.get('color','-'),printing=body.get('printing','-'),width_mm=mm(body.get('width',{})),length_mm=mm(body.get('length',{})),height_mm=mm(body.get('height',{})),gusset_mm=mm(body.get('gusset',{})),thickness_mm=thick(t),tol_dim_lo=float(body.get('tol_dim_lo',-10)),tol_dim_hi=float(body.get('tol_dim_hi',10)),tol_thickness=float(body.get('tol_thickness',.01)),length_datum=body.get('length_datum','opening_to_bottom'),display_unit=body.get('display_unit','mm'),holes_count=int(body.get('holes_count',0)),holes_dia=body.get('holes_dia',''),label_w=float(body.get('label_w',0)),label_h=float(body.get('label_h',0)),extra_notes=body.get('extra_notes',[]))
    spec.drawing_view=body.get('drawing_view','2d')
    return spec

class H(BaseHTTPRequestHandler):
    def out(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False,default=str).encode();self.send_response(status);self.send_header('content-type','application/json; charset=utf-8');self.send_header('access-control-allow-origin','*');self.send_header('content-length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def body(self): return json.loads(self.rfile.read(int(self.headers.get('content-length','0'))) or b'{}')
    def do_GET(self):
        parsed=urlparse(self.path); path=parsed.path; query=parse_qs(parsed.query); q=(query.get('q') or [''])[0].strip().lower()
        if path=='/api/meta': return self.out(META)
        if path=='/api/customers':
            grouped={}
            for f in [saved_form(r) for r in saved_rows()]+[legacy_form(r) for r in legacy_rows()]:
                key=(f['customer_code'],f['customer'])
                if key != ('',''): grouped[key]=grouped.get(key,0)+1
            return self.out({'rows':[{'customer_code':k[0],'customer':k[1],'times':v} for k,v in grouped.items()]})
        if self.path.startswith('/api/health'): return self.out({'ok':True,'mode':'visual-review'})
        if self.path.startswith('/api/drawings'): return self.out({'rows':[]})
        if path=='/api/history':
            rows=[saved_history(r) for r in reversed(saved_rows())]+[legacy_history(r) for r in legacy_rows()]
            if q: rows=[r for r in rows if q in ' '.join(str(v) for v in r.values()).lower()]
            for name, fields in [('customer',('customer','customer_code')),('item',('item','product','ref')),('size',('size',)),('product_key',('_product_key',))]:
                value=(query.get(name) or [''])[0].strip().casefold()
                if value: rows=[r for r in rows if any(value in str(r.get(k,'')).casefold() for k in fields)]
            for name, lower in [('date_from',True),('date_to',False)]:
                value=(query.get(name) or [''])[0].strip()
                if value: rows=[r for r in rows if r.get('date') and ((r['date']>=value) if lower else (r['date']<=value))]
            order=(query.get('sort') or ['newest'])[0]
            rows.sort(key=lambda r:(r.get('date',''),r.get('ref','')),reverse=order!='oldest')
            return self.out({'rows':rows,'count_text':f'พบ {len(rows)} รายการ (รวมฉบับแก้ไขในเครื่องทดลอง)'})
        if path=='/api/planning/sources':
            rows=[legacy_source(r) for r in legacy_rows()]
            if q: rows=[r for r in rows if q in r['line'].lower()]
            return self.out({'rows':[{'quote_ref':r['quote_ref'],'line':r['line']} for r in rows]})
        if self.path.startswith('/api/planning/source'): return self.out({'quote_ref':'QT-20260830-0001','line':DEMO_LINE,'width':'10.16','length':'30.48','thickness':'0.16','gusset':'0','package':'100 pcs/pack','quantity':'1000','summary':'QT-20260830-0001 • CSK • PE BAG 4 x 12 inch','status':'Pricing and approved drawing loaded into Planning','product_key':'flat','sack_quantity':'500','sack_weight_kg':'9.2000','grams_per_item':'18.400','items_per_kg':'54.35','adjusted_items':'48.91','tolerance_width_mm':'10','tolerance_length_mm':'10','tolerance_thickness_mm':'0.01','drawing_doc_no':'DFA-2026-0001','special_features':'ซีลก้นตรงและแข็งแรง / Straight, strong bottom seal\nปากถุงเปิดง่าย / Easy-open bag mouth\nห้ามมีรอยย่น รอยขาด หรือสิ่งปนเปื้อน / No wrinkles, tears or contamination','sales_product':'PE BAG 4 x 12 inch','sales_part_no':'4P677198-1','sales_size':'4 x 12 inch x 0.16 mm/pair','sales_width':'4 inch','sales_length':'12 inch','sales_thickness':'0.16 mm','sales_thickness_mode':'ต่อคู่ / Per Pair','sale_basis':'piece','small_pack_quantity':'100','package_count_per_sack':'5'})
        if path.startswith('/api/quotations/') and path.endswith('/form'):
            ref=path[len('/api/quotations/'):-len('/form')].strip('/')
            local=find_saved(ref)
            if local:
                actual=local['quote_ref']
                return self.out({'quote_ref':actual,'form':saved_form(local),'ref_text':actual,'status':'ดึงฉบับที่บันทึกในเครื่องทดลองแล้ว'})
            row=find_legacy(ref)
            if not row: return self.out({'detail':'ไม่พบรายการเดิมที่เลือก'},404)
            actual=legacy_ref(row)
            return self.out({'quote_ref':actual,'form':legacy_form(row),'ref_text':actual,'status':'ดึงข้อมูลจากฐานข้อมูลเดิมแล้ว'})
        sample={'quote_ref':'QT-20260830-0001','line':DEMO_LINE,'customer':'CSK Plasatic Co.,Ltd','customer_code':'CSK','part_no':'4P677198-1','product':'PE BAG 4 x 12 inch','size_text':'4 x 12 inch','width_mm':101.6,'length_mm':304.8,'thickness_mm':0.16,'thickness_mode':'pair','product_key':'flat','gusset_mm':0,'tolerance_width_mm':10,'tolerance_length_mm':10,'tolerance_thickness_mm':.01,'width_original':{'value':4,'unit':'นิ้ว'},'length_original':{'value':12,'unit':'นิ้ว'},'gusset_original':{'value':0,'unit':'นิ้ว'},'thickness_original':{'value':.16,'unit':'มม.'}}
        if path in {'/api/sample-inspections/sources','/api/coa/sources'}:
            rows=[saved_source(r) for r in reversed(saved_rows())]+[legacy_source(r) for r in legacy_rows()]
            if q: rows=[r for r in rows if q in r['line'].lower()]
            return self.out({'rows':rows})
        if self.path.startswith('/api/coa') or self.path.startswith('/api/sample-inspections'): return self.out({'rows':[]})
        return self.out({'rows':[]})
    def do_POST(self):
        try:
            b=self.body()
            if self.path=='/api/auth/login': return self.out({'token':'demo-token','expires_at':int(time.time())+86400,'user':{'id':1,'email':'demo@pantong.local','full_name':'Demo User'}})
            if self.path=='/api/calculate': return self.out(calc(b))
            if self.path=='/api/planning/compare':
                ref_thickness, ref_grams = 0.16, 18.4
                new_thickness = float(b.get('thickness') or ref_thickness)
                new_grams = ref_grams * new_thickness / ref_thickness
                pcs_per_kg = 1000 / new_grams
                adjusted = pcs_per_kg * 0.9
                sack_qty = float(b.get('sack_quantity') or 0)
                return self.out({'line':f'จำนวนใบเท่ากัน • ความหนา {new_thickness:g} mm • น้ำหนักใหม่ {new_grams:.3f} g/ใบ','grams_per_item':f'{new_grams:.3f}','items_per_kg':f'{pcs_per_kg:.2f}','adjusted_items':f'{adjusted:.2f}','sack_weight_kg':f'{new_grams*sack_qty/1000:.4f}' if sack_qty else ''})
            if self.path=='/api/drawing': return self.out({'svg':render_svg(drawing(b))})
            if self.path=='/api/drawing/html': return self.out({'html':render_html(drawing(b))})
            if self.path=='/api/quotations':
                with SAVED_LOCK:
                    rows=saved_rows(); ref=saved_ref(b,rows); created=time.strftime('%Y-%m-%dT%H:%M:%S')
                    rows.append({'id':len(rows)+1,'quote_ref':ref,'created_at':created,'body':b})
                    write_saved(rows)
                return self.out({'quote_ref':ref,'id':len(rows),'created_at':created})
            return self.out({'detail':'This action is disabled in visual-review mode'},400)
        except Exception as e: return self.out({'detail':str(e)},400)
    def log_message(self,*a): pass

ThreadingHTTPServer(('127.0.0.1',int(os.environ.get('PANTONG_API_PORT', '8100'))),H).serve_forever()
