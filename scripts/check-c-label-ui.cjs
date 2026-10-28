// Real local document API/UI; chat calls are blocked. No uploads or document mutations.
const { chromium } = require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const base = 'http://localhost:5174';
  const data = path.join(process.env.LOCALAPPDATA, 'Temp/mathrag-c-integration-20261028');
  const out = path.join(data, 'labels-codex-20261028');
  const account = JSON.parse(fs.readFileSync(path.join(data, 'browser-account.json'), 'utf8'));
  const budget = fs.readFileSync(path.join(data, 'budget.json'), 'utf8');
  const browser = await chromium.launch({ headless: true, executablePath: path.join(process.env.LOCALAPPDATA,
    'ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-win64/chrome-headless-shell.exe') });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.route(/\/api\/(?:public\/)?chat\/stream/, route => route.abort());
    const auth = await context.request.post(base + '/api/auth/login', { data: account, headers: { Origin: base } });
    assert.equal(auth.status(), 200);
    const kbs = (await (await context.request.get(base + '/api/kbs')).json()).data;
    const kb = kbs.find(row => row.name === '数学真实联调资料');
    const docs = (await (await context.request.get(base + '/api/docs?kb_id=' + kb.id)).json()).data;
    assert.equal(docs.length, 171);
    assert(docs.every(doc => doc.knowledge_points.length && doc.difficulty));
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto(base);
    await page.getByRole('button', { name: '资料：数学真实联调资料', exact: true }).click();
    await page.getByRole('button', { name: '管理资料', exact: true }).click();
    const drawer = page.locator('.el-drawer');
    await drawer.locator('.doc-list li').first().waitFor();
    assert.equal(await drawer.locator('.doc-list li').count(), docs.length);
    await drawer.locator('select[id$="-knowledge"]').selectOption({ label: '伴随矩阵' });
    await drawer.locator('select[id$="-type"]').selectOption({ label: '计算题' });
    await drawer.locator('select[id$="-difficulty"]').selectOption({ label: '基础' });
    const expected = docs.filter(doc => doc.knowledge_points.includes('伴随矩阵')
      && doc.question_types.includes('计算题') && doc.difficulty === '基础');
    assert(expected.length > 0);
    assert.equal(await drawer.locator('.doc-list li').count(), expected.length);
    await drawer.locator('.doc-list li .doc-auto-tags').first().getByText('伴随矩阵', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(out, 'real-tag-filters.png'), fullPage: true });
    await drawer.getByRole('button', { name: '清除筛选', exact: true }).click();
    await drawer.locator('select[id$="-status"]').selectOption('tagged');
    assert.equal(await drawer.locator('.doc-list li').count(), 171);
    assert.deepEqual(errors, []);
    assert.equal(fs.readFileSync(path.join(data, 'budget.json'), 'utf8'), budget);
    const result = { real_api_tagged_docs: docs.length, combined_filter_results: expected.length,
      tagged_filter_results: 171, page_errors: errors, paid_model_calls: 0,
      fixture_labels_injected: false, note: 'Actual current-chat model labels loaded from the real database.' };
    fs.writeFileSync(path.join(out, 'browser-result.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
