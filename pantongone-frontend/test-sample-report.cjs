// Supply PLAYWRIGHT_MODULE and PDF_LIB_MODULE when using a bundled tool runtime.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { transformSync } = require('esbuild');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { PDFDocument } = require(process.env.PDF_LIB_MODULE || 'pdf-lib');

const filename = path.join(__dirname, 'src/panels/SampleInspection.report.ts');
const code = transformSync(fs.readFileSync(filename, 'utf8'), { loader: 'ts', format: 'cjs' }).code;
const compiled = { exports: {} };
new Function('module', 'exports', code)(compiled, compiled.exports);
const { sampleReportHtml } = compiled.exports;
const output = process.env.QA_OUTPUT || fs.mkdtempSync(path.join(os.tmpdir(), 'pantong-report-'));
fs.mkdirSync(output, { recursive: true });
const source = {
  quote_ref: 'QT-TEST', quote_version: 1, customer: 'Synthetic customer', customer_code: 'TEST', part_no: 'PART-01',
  product: 'Gusset sample review', product_key: 'gusset', width_mm: 200, length_mm: 400, gusset_mm: 50,
  thickness_mm: .076, thickness_mode: 'pair', width_original: { value: 20, unit: 'ซม.' },
  length_original: { value: 40, unit: 'ซม.' }, gusset_original: { value: 5, unit: 'ซม.' },
  thickness_original: { value: .076, unit: 'มม.' },
};
const record = {
  id: 1, revision: 1, quote_ref: 'QT-TEST', report_no: 'SI-20261008-0001', source_snapshot: source,
  length_datum: 'opening_to_bottom', inspection_date: '2026-10-08',
  tolerance_width_mm: 0, tolerance_length_mm: 0, tolerance_thickness_mm: .005,
  tolerance_gusset_left_mm: 0, tolerance_gusset_right_mm: 0,
  results_json: [1, 2, 3].map(() => ({ width: 200, length: 400, thickness: .076, gusset_left: 50, gusset_right: 50 })),
  remarks: 'Synthetic QA: both gussets and original source remain visible.', checked_by: 'Inspector', approved_by: 'Reviewer',
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1100, height: 800 } });
    await page.emulateMedia({ media: 'print' });
    for (const [name, sample] of [
      ['normal', record],
      ['long-remarks', { ...record, remarks: Array.from({ length: 70 }, (_, index) => `Remark ${index + 1}: All measured dimensions and customer notes must remain visible.`).join('\n') }],
    ]) {
      const html = sampleReportHtml(sample);
      await page.setContent(html);
      await page.evaluate(() => document.fonts.ready);
      await page.screenshot({ path: path.join(output, `${name}.png`), fullPage: true });
      const bytes = await page.pdf({ path: path.join(output, `${name}.pdf`), preferCSSPageSize: true, printBackground: true });
      const pdf = await PDFDocument.load(bytes);
      const count = pdf.getPageCount();
      if (name === 'normal') assert.equal(count, 1, 'The normal five-row gusset report must fit one A4 page');
      else {
        assert(count > 1, 'Long remarks must flow onto additional pages');
        assert.equal(await page.locator('.long-remarks').count(), 1);
        assert((await page.locator('.long-remarks').innerText()).includes('Remark 70:'));
      }
      for (const sheet of pdf.getPages()) {
        const size = sheet.getSize();
        assert(Math.abs(size.width - 841.89) < 2 && Math.abs(size.height - 595.28) < 2, 'Landscape A4 required');
      }
      const overflow = await page.evaluate(() => document.body.scrollWidth > document.documentElement.clientWidth);
      assert.equal(overflow, false, 'Report must not clip horizontally');
      assert((await page.locator('.approval').innerText()).includes('Name / Signature'));
      assert((await page.locator('table').innerText()).includes('Gusset Right'));
      console.log(`${name}: ${count} landscape A4 page(s), full remarks and signature blocks present`);
    }
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
