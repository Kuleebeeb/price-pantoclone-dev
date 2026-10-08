// Run only against a disposable local API. PLAYWRIGHT_MODULE may point to a bundled runtime.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.BASE;
if (process.env.PANTONGONE_DISPOSABLE_TEST !== '1' || !base || !['127.0.0.1', 'localhost'].includes(new URL(base).hostname)) {
  throw new Error('Explicit disposable loopback API required');
}
const output = process.env.QA_OUTPUT;
if (!output) throw new Error('QA_OUTPUT is required');
fs.mkdirSync(output, { recursive: true });
const email = process.env.BOOTSTRAP_EMAIL || 'smoke@test.local';
const password = process.env.BOOTSTRAP_PASSWORD || 'smoke-pass-1234';
const json = async (url, options) => {
  const response = await fetch(base + url, options);
  const body = await response.json();
  assert.equal(response.status, 200, JSON.stringify(body));
  return body;
};

(async () => {
  const session = await json('/api/auth/login', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ email, password }) });
  const headers = { 'content-type': 'application/json', authorization: `Bearer ${session.token}` };
  const quote = await json('/api/quotations', { method: 'POST', headers, body: JSON.stringify({
    customer: 'QA Browser synthetic', customer_code: 'QABROWSER', item_description: 'Gusset sample review', quote_date: '2026-10-08',
    calc: { product_key: 'gusset', width: { value: 20, unit: 'ซม.' }, length: { value: 40, unit: 'ซม.' },
      gusset: { value: 5, unit: 'ซม.' }, thickness: { value: 0.16, unit: 'มม.', mode: 'pair' },
      density_g_cm3: 0.92, material_price_per_kg: 65, sale_basis: 'kg', selling_price_per_kg_override: 85,
      pack_quantity: 100, sack_quantity: 1000, order_quantity: 1000 },
  }) });
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
    const pageErrors = [];
    page.on('pageerror', error => pageErrors.push(String(error)));
    await page.goto(base + '/');
    await page.getByLabel(/Email/).fill(email);
    await page.getByLabel(/Password/).fill(password);
    await page.getByLabel(/Password/).press('Enter');
    await page.getByRole('tab', { name: 'Sample Inspection', exact: true }).click();
    await page.locator('.sample-card input.wide').fill(quote.quote_ref);
    await page.locator('.choices button').filter({ hasText: quote.quote_ref }).click();
    await page.getByRole('button', { name: /Opening to Bottom/ }).click();
    await page.getByRole('textbox', { name: /^Remarks/ }).fill('Synthetic QA: both gussets and original source remain visible.');
    await page.getByRole('button', { name: 'Save', exact: true }).click();
    await page.getByRole('status').filter({ hasText: 'SI-' }).waitFor();
    const incomplete = await json('/api/sample-inspections', { headers });
    const saved = incomplete.rows.find(row => row.quote_ref === quote.quote_ref);
    assert.equal(saved.overall_result, 'WAITING');
    assert.equal(saved.length_datum, 'opening_to_bottom');
    assert.equal(saved.source_snapshot.width_mm, 200);
    const values = { Width: '200', Length: '400', Thickness: '0.16', 'Gusset Left': '50', 'Gusset Right': '50' };
    for (const [label, value] of Object.entries(values)) {
      const row = page.locator('.sample table').first().getByRole('row').filter({ has: page.getByRole('cell', { name: label, exact: true }) });
      const cells = row.locator('input[type="number"]');
      assert.equal(await cells.count(), 3);
      for (let i = 0; i < 3; i++) await cells.nth(i).fill(value);
    }
    const popupPromise = page.waitForEvent('popup');
    await page.getByRole('button', { name: /Save & Print/ }).click();
    const popup = await popupPromise;
    await popup.getByText('SAMPLE INSPECTION REPORT', { exact: false }).first().waitFor();
    assert.match(await popup.locator('body').innerText(), /Gusset Right/);
    assert.match(await popup.locator('body').innerText(), /OPENING TO BOTTOM/);
    await popup.screenshot({ path: path.join(output, 'sample-report.png'), fullPage: true });
    const samplePdf = await popup.pdf({ path: path.join(output, 'sample-report.pdf'), preferCSSPageSize: true, printBackground: true });
    // Chromium emits page dictionaries directly; also visually inspect the rendered PDF.
    assert.equal((samplePdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length, 1, 'ordinary gusset sample fits one A4 page');
    await page.screenshot({ path: path.join(output, 'sample-editor.png'), fullPage: true });
    const complete = (await json('/api/sample-inspections', { headers })).rows.find(row => row.id === saved.id);
    assert.equal(complete.overall_result, 'PASS');
    assert.equal(complete.report_no, saved.report_no);
    assert.equal(complete.revision, 2);
    await page.reload();
    await page.getByRole('tab', { name: 'Sample Inspection', exact: true }).click();
    const history = page.locator('.sample-card').last().getByRole('row').filter({ hasText: saved.report_no });
    await history.getByRole('button', { name: 'Edit', exact: true }).click();
    assert.equal(await page.getByRole('button', { name: /Opening to Bottom/ }).locator('input').isChecked(), true);
    assert.equal(await page.getByRole('textbox', { name: /^Remarks/ }).inputValue(), 'Synthetic QA: both gussets and original source remain visible.');
    await history.getByRole('button', { name: 'Print', exact: true }).click();
    const afterPrint = (await json('/api/sample-inspections', { headers })).rows.find(row => row.id === saved.id);
    assert.equal(afterPrint.revision, 2);
    assert.equal(afterPrint.report_no, saved.report_no);
    const drawing = await json('/api/drawing/html', { method: 'POST', headers, body: JSON.stringify({
      product_key: 'cover', doc_no: 'DFA-QA-COVER', customer: 'QA Browser synthetic', title: 'Open bottom cover',
      width: { value: 45, unit: 'ซม.' }, length: { value: 60, unit: 'ซม.' }, height: { value: 1.5, unit: 'เมตร' },
      thickness: { value: 0.08, unit: 'มม.', mode: 'side' }, drawing_view: 'both', date: '2026-10-08',
    }) });
    const drawingPage = await browser.newPage({ viewport: { width: 1440, height: 1080 } });
    await drawingPage.setContent(drawing.html);
    await drawingPage.evaluate(() => document.fonts.ready);
    const drawingText = await drawingPage.locator('body').innerText();
    assert.match(drawingText, /OPEN BOTTOM/);
    assert.match(drawingText, /Printed:/);
    assert.match(drawingText, /Page 1 of 1/);
    await drawingPage.screenshot({ path: path.join(output, 'cover-drawing.png'), fullPage: true });
    const drawingPdf = await drawingPage.pdf({ path: path.join(output, 'cover-drawing.pdf'), preferCSSPageSize: true, printBackground: true });
    assert.equal((drawingPdf.toString('latin1').match(/\/Type\s*\/Page\b/g) || []).length, 1, 'cover drawing fits one A4 page');
    assert.deepEqual(pageErrors, []);
    console.log(JSON.stringify({ result: 'PASS', report: saved.report_no, checks: ['login', 'incomplete WAITING', 'datum persisted', 'three samples PASS', 'both gussets printed', 'same number on update/reprint', 'reopen restores data', 'one page A4 sample', 'cover units and one page A4 drawing', 'no browser runtime errors'], artifacts: output }));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
