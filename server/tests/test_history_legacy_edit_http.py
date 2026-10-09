"""Regression for imported quote editing, part numbers, and original audit values."""
import copy
import json
import os
from urllib.parse import urlparse, quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from uuid import uuid4

import psycopg
from psycopg.types.json import Jsonb

BASE = os.environ.get('BASE', '').rstrip('/')
DSN = os.environ.get('DATABASE_URL', '')
if (os.environ.get('PANTONGONE_DISPOSABLE_TEST') != '1'
        or 'smoke' not in urlparse(DSN).path
        or urlparse(BASE).hostname not in {'localhost', '127.0.0.1', 'api'}):
    raise SystemExit('Explicit disposable local API and smoke database required')
token = ''

def call(method, path, body=None):
    req = Request(BASE + path, method=method,
                  data=json.dumps(body).encode() if body is not None else None,
                  headers={'content-type': 'application/json', **({'authorization': 'Bearer ' + token} if token else {})})
    with urlopen(req, timeout=20) as response:
        return json.load(response)

token = call('POST', '/api/auth/login', {'email': os.environ.get('BOOTSTRAP_EMAIL', 'smoke@test.local'),
                                      'password': os.environ.get('BOOTSTRAP_PASSWORD', 'smoke-pass-1234')})['token']
run = uuid4().hex[:10]
calc = {'product_key': 'flat', 'width': {'value': 20, 'unit': 'ซม.'},
        'length': {'value': 40, 'unit': 'ซม.'}, 'thickness': {'value': .16, 'unit': 'มม.', 'mode': 'pair'},
        'bottom_allowance': {'value': 2, 'unit': 'ซม.'}, 'density_g_cm3': .92, 'material_price_per_kg': 65,
        'sale_basis': 'kg', 'selling_price_per_kg_override': 85, 'order_quantity': 1000}
body = {'customer': 'Synthetic legacy ' + run, 'customer_code': run, 'product_reference': 'PART-' + run,
        'item_description': 'Synthetic legacy bag', 'quote_date': '2026-10-09', 'calc': calc, 'request_id': str(uuid4())}
created = call('POST', '/api/quotations', body)
ref = created['quote_ref']
with psycopg.connect(DSN) as conn:
    inputs = conn.execute('SELECT inputs_json FROM quotations WHERE quote_ref=%s', (ref,)).fetchone()[0]
    inputs['dimensions'] = {key: inputs.pop(key) for key in ('width', 'length', 'height', 'gusset', 'sold_length')}
    inputs['import_original_source'] = 'synthetic-book'
    inputs['import_provenance'] = {'result_origin': 'stored', 'calculator_compatible': True}
    conn.execute('UPDATE quotations SET inputs_json=%s WHERE quote_ref=%s', (Jsonb(inputs), ref))
path = '/api/quotations/' + quote(ref, safe='') + '/form'
old = call('GET', path)['form']
assert old['width'] == '20' and old['length'] == '40'
assert old['bottom_allowance'] == '2' and old['thickness'] == '0.16'
history = call('GET', '/api/history?customer=' + quote(body['customer']))['rows'][0]
assert history['product'] == body['product_reference'], history['product']
assert '0.16' in history['size'], history['size']

new_calc = copy.deepcopy(calc)
new_calc['width']['value'] = 30
new_calc['length']['value'] = 50
changed = call('POST', '/api/quotations', {**body, 'calc': new_calc, 'update_ref': ref,
                                        'expected_version': created['version'], 'request_id': str(uuid4())})
assert changed['quote_ref'] == ref and changed['version'] == 2
current = call('GET', path)['form']
assert current['width'] == '30' and current['length'] == '50', current
assert current['thickness'] == '0.16'
history = call('GET', '/api/history?customer=' + quote(body['customer']))['rows'][0]
assert '30.0' in history['size'] and '50.0' in history['size'], history['size']
assert history['_input_details'].count('30.0 ซม.') == 1
assert 'import_provenance' not in history['_input_details']
with psycopg.connect(DSN) as conn:
    saved = conn.execute('SELECT inputs_json FROM quotations WHERE quote_ref=%s', (ref,)).fetchone()[0]
    assert saved['width'] == saved['dimensions']['width'] == new_calc['width']
    assert saved['import_original_source'] == 'synthetic-book'
    before, after = conn.execute("SELECT before_json,after_json FROM document_audit WHERE entity_type='quotation' AND entity_id=%s AND action='update' ORDER BY id DESC LIMIT 1", (ref,)).fetchone()
    assert before['inputs_json']['dimensions']['width']['value'] == 20
    assert after['inputs_json']['dimensions']['width']['value'] == 30
legacy_cover = call('POST', '/api/quotations', {**body, 'calc': {**calc, 'product_key': 'cover', 'height': {'value': 100, 'unit': 'ซม.'}}, 'request_id': str(uuid4())})
with psycopg.connect(DSN) as conn:
    cover_inputs = conn.execute('SELECT inputs_json FROM quotations WHERE quote_ref=%s', (legacy_cover['quote_ref'],)).fetchone()[0]
    cover_inputs['import_provenance'] = {'source_kind': 'sqlite', 'result_origin': 'stored', 'calculator_compatible': False}
    cover_inputs.pop('roof_gsm', None)
    cover_inputs.pop('mesh_gsm', None)
    conn.execute('UPDATE quotations SET inputs_json=%s WHERE quote_ref=%s', (Jsonb(cover_inputs), legacy_cover['quote_ref']))
cover_path = '/api/quotations/' + quote(legacy_cover['quote_ref'], safe='')
cover_form = call('GET', cover_path + '/form')
assert cover_form['calculator_compatible'] is False and 'calculation or quantity convention' in cover_form['calculator_warning']
try:
    call('POST', '/api/quotations', {**body, 'update_ref': legacy_cover['quote_ref'], 'expected_version': 1, 'request_id': str(uuid4())})
except HTTPError as error:
    assert error.code == 409
else:
    raise AssertionError('An incompatible historical calculator must not be silently replaced')
with psycopg.connect(DSN) as conn:
    assert conn.execute('SELECT version FROM quotations WHERE quote_ref=%s', (legacy_cover['quote_ref'],)).fetchone()[0] == 1
print('PASS: legacy edit/reopen/history, Part No., flat thickness/allowance fallback, audit and provenance')
