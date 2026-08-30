"""Local visual-review API: real calculator/drawing core, no database writes."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import json, sys, time

ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'server'/'core'))
from calculator import *
from drawing import DrawingSpec, PRODUCT_TO_SHAPE, render_svg, render_html

META=json.loads((ROOT/'pantongone-frontend'/'src'/'test-fixtures'/'meta.json').read_text(encoding='utf-8'))
META['default_weight_formulas']=DEFAULT_WEIGHT_FORMULAS
META['default_price_formula']=DEFAULT_PRICE_FORMULA
DEMO_LINE='QT-20260830-0001 | CSK | CSK Plasatic Co.,Ltd | PE BAG 4 x 12 inch'
DEMO_FORM={'customer':'CSK Plasatic Co.,Ltd','customer_code':'CSK','quote_date':'2026-08-30','item_description':'PE BAG 4 x 12 inch','product_reference':'4P677198-1','product_key':'flat','width':'4','width_unit':'นิ้ว','length':'12','length_unit':'นิ้ว','height':'','gusset':'','thickness':'0.16','thickness_unit':'มม.','thickness_mode':'pair','length_reference':'ปากถึงก้นถุง / Opening to Bottom','tolerance_width':'10','tolerance_length':'10','tolerance_thickness':'0.01','tolerance_gusset_left':'','tolerance_gusset_right':'','special_requirements':'ซีลก้นตรงและแข็งแรง\nปากถุงเปิดง่าย\nห้ามมีรอยย่น รอยขาด หรือสิ่งปนเปื้อน'}

def measure(x): return to_cm(float(x.get('value',0) or 0),x.get('unit','ซม.'))
def mm(x): return measure(x)*10
def thick(x): return thickness_to_mm(float(x.get('value',0) or 0),x.get('unit','มม.'))
def fmt(v,d=3): return f'{v:,.{d}f}'

def calc(body):
    key=body.get('product_key','flat'); width=measure(body.get('width',{})); length=measure(body.get('length',{})); gusset=measure(body.get('gusset',{})); height=measure(body.get('height',{})); sold=measure(body.get('sold_length',{}))/100
    allowance=measure(body.get('bottom_allowance',{})) if key in {'flat','gusset'} else 0
    ti=thick(body.get('thickness',{})); mode=body.get('thickness',{}).get('mode','pair')
    material=float(body.get('material_price_per_kg',65)); basis=float(body.get('selling_price_per_kg_override',0)); markup=((basis/material)-1)*100 if material and basis else 0
    formula=body.get('weight_formula') or DEFAULT_WEIGHT_FORMULAS[key]
    r=calculate(product_key=key,width_cm=width,length_cm=length,height_cm=height,gusset_cm=gusset,sold_length_m=sold,bottom_allowance_cm=allowance,thickness_input_mm=ti,thickness_mode=mode,density_g_cm3=float(body.get('density_g_cm3',.92)),roof_gsm=float(body.get('roof_gsm',120)),mesh_gsm=float(body.get('mesh_gsm',80)),material_price_per_kg=material,markup_percent=markup,deduction_percent=float(body.get('deduction_percent',10)),pack_quantity=float(body.get('pack_quantity',0)),sack_quantity=float(body.get('sack_quantity',0)),apply_deduction=bool(body.get('apply_deduction',True)),sell_by_kg=body.get('sale_basis','kg')=='kg',selling_price_per_piece_override=float(body.get('selling_price_per_piece_override',0)),selling_price_per_kg_override=basis,order_quantity=float(body.get('order_quantity',1000)),control_min_g=float(body.get('control_min_g',0)),control_max_g=float(body.get('control_max_g',0)),weight_formula=formula,price_formula=body.get('price_formula') or DEFAULT_PRICE_FORMULA)
    display={'grams':fmt(r.grams_per_item)+' กรัม','items_per_kg':fmt(r.items_per_kg,2)+' ชิ้น','adjusted_items':fmt(r.production_items_per_kg,2)+' ชิ้น','calculated_piece':fmt(r.calculated_price_per_piece_from_kg)+' บาท/ชิ้น','primary_line':f'น้ำหนัก {fmt(r.grams_per_item)} g • {fmt(r.items_per_kg,2)} ชิ้น/กก.','derivation':'','size_text':f'{width:g} × {length:g} cm','deduction_caption':'หลังหักเผื่อผลิต','roof_area':'','mesh_area':''}
    return {'results':r.variables,'normalized':{'width_cm':width,'length_cm':length,'gusset_cm':gusset,'thickness_input_mm':ti},'display':display,'human_summary':f'Weight {fmt(r.grams_per_item)} g/pc • Theoretical {fmt(r.items_per_kg,2)} pcs/kg • Adjusted {fmt(r.production_items_per_kg,2)} pcs/kg','price_basis':'DEMO','formulas':{'weight':formula,'price':body.get('price_formula') or DEFAULT_PRICE_FORMULA}}

def drawing(body):
    t=body.get('thickness',{})
    spec=DrawingSpec(doc_no=body.get('doc_no') or 'DEMO-DWG-001',customer=body.get('customer',''),title=body.get('title','') or body.get('product','SAMPLE DRAWING'),shape=PRODUCT_TO_SHAPE[body.get('product_key','flat')],revision=body.get('revision','A'),date=body.get('date',''),part_no=body.get('part_no','-'),customer_code=body.get('customer_code',''),material=body.get('material','POLYETHYLENE'),color=body.get('color','-'),printing=body.get('printing','-'),width_mm=mm(body.get('width',{})),length_mm=mm(body.get('length',{})),height_mm=mm(body.get('height',{})),gusset_mm=mm(body.get('gusset',{})),thickness_mm=thick(t),tol_dim_lo=float(body.get('tol_dim_lo',-10)),tol_dim_hi=float(body.get('tol_dim_hi',10)),tol_thickness=float(body.get('tol_thickness',.01)),length_datum=body.get('length_datum','opening_to_bottom'),display_unit=body.get('display_unit','mm'),holes_count=int(body.get('holes_count',0)),holes_dia=body.get('holes_dia',''),label_w=float(body.get('label_w',0)),label_h=float(body.get('label_h',0)),extra_notes=body.get('extra_notes',[]))
    return spec

class H(BaseHTTPRequestHandler):
    def out(self,obj,status=200):
        raw=json.dumps(obj,ensure_ascii=False,default=str).encode();self.send_response(status);self.send_header('content-type','application/json; charset=utf-8');self.send_header('access-control-allow-origin','*');self.send_header('content-length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def body(self): return json.loads(self.rfile.read(int(self.headers.get('content-length','0'))) or b'{}')
    def do_GET(self):
        if self.path.startswith('/api/meta'): return self.out(META)
        if self.path.startswith('/api/customers'): return self.out({'rows':[{'customer':'CSK Plasatic Co.,Ltd','customer_code':'CSK','times':1}]})
        if self.path.startswith('/api/health'): return self.out({'ok':True,'mode':'visual-review'})
        if self.path.startswith('/api/drawings'): return self.out({'rows':[]})
        if self.path.startswith('/api/planning/sources'): return self.out({'rows':[{'quote_ref':'QT-20260830-0001','line':DEMO_LINE}]})
        if self.path.startswith('/api/planning/source'): return self.out({'quote_ref':'QT-20260830-0001','line':DEMO_LINE,'width':'10.16','length':'30.48','thickness':'0.16','gusset':'0','package':'100 pcs/pack','quantity':'1000','summary':'QT-20260830-0001 • CSK • PE BAG 4 x 12 inch','status':'Pricing and approved drawing loaded into Planning','product_key':'flat','sack_quantity':'500','sack_weight_kg':'9.2000','grams_per_item':'18.400','items_per_kg':'54.35','adjusted_items':'48.91','tolerance_width_mm':'10','tolerance_length_mm':'10','tolerance_thickness_mm':'0.01','drawing_doc_no':'DFA-2026-0001','special_features':'ซีลก้นตรงและแข็งแรง / Straight, strong bottom seal\nปากถุงเปิดง่าย / Easy-open bag mouth\nห้ามมีรอยย่น รอยขาด หรือสิ่งปนเปื้อน / No wrinkles, tears or contamination','sales_product':'PE BAG 4 x 12 inch','sales_part_no':'4P677198-1','sales_size':'4 x 12 inch x 0.16 mm/pair','sales_width':'4 inch','sales_length':'12 inch','sales_thickness':'0.16 mm','sales_thickness_mode':'ต่อคู่ / Per Pair','sale_basis':'piece','small_pack_quantity':'100','package_count_per_sack':'5'})
        if self.path.startswith('/api/quotations/') and self.path.endswith('/form'): return self.out({'quote_ref':'QT-20260830-0001','form':DEMO_FORM,'ref_text':'DEMO','status':'Quotation loaded'})
        sample={'quote_ref':'QT-20260830-0001','line':DEMO_LINE,'customer':'CSK Plasatic Co.,Ltd','customer_code':'CSK','part_no':'4P677198-1','product':'PE BAG 4 x 12 inch','size_text':'4 x 12 inch','width_mm':101.6,'length_mm':304.8,'thickness_mm':0.16,'thickness_mode':'pair','product_key':'flat','gusset_mm':0,'tolerance_width_mm':10,'tolerance_length_mm':10,'tolerance_thickness_mm':.01,'width_original':{'value':4,'unit':'นิ้ว'},'length_original':{'value':12,'unit':'นิ้ว'},'gusset_original':{'value':0,'unit':'นิ้ว'},'thickness_original':{'value':.16,'unit':'มม.'}}
        if self.path.startswith('/api/sample-inspections/sources'): return self.out({'rows':[sample]})
        if self.path.startswith('/api/coa/sources'): return self.out({'rows':[sample]})
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
            if self.path=='/api/quotations': return self.out({'quote_ref':'DEMO-QT-001','id':1,'created_at':'demo'})
            return self.out({'detail':'This action is disabled in visual-review mode'},400)
        except Exception as e: return self.out({'detail':str(e)},400)
    def log_message(self,*a): pass

ThreadingHTTPServer(('127.0.0.1',8100),H).serve_forever()
