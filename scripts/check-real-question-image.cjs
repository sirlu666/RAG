// Real image OCR through Nginx. Never sends a paid question or uploads a document.
const { chromium } = require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const file = process.argv[2];
  if (!file) throw new Error('Pass the user image path as the first argument.');
  const base = 'http://localhost:8086';
  const data = path.join(process.env.LOCALAPPDATA, 'Temp/mathrag-c-integration-20261028');
  const out = path.join(data, 'question-image-fix-20261028');
  fs.mkdirSync(out, { recursive: true });
  const account = JSON.parse(fs.readFileSync(path.join(data, 'browser-account.json'), 'utf8'));
  const budget = fs.readFileSync(path.join(data, 'budget.json'), 'utf8');
  const browser = await chromium.launch({ headless: true, executablePath: path.join(process.env.LOCALAPPDATA,
    'ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-win64/chrome-headless-shell.exe') });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    let paidRequests = 0, uploadRequests = 0;
    await context.route(/\/api\/(?:public\/)?chat\/stream/, route => { paidRequests++; return route.abort(); });
    await context.route('**/api/docs/upload', route => { uploadRequests++; return route.abort(); });
    const auth = await context.request.post(base + '/api/auth/login', { data: account, headers: { Origin: base } });
    assert.equal(auth.status(), 200);
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto(base);
    await page.getByRole('button', { name: '资料：数学真实联调资料', exact: true }).click();
    const chat = page.locator('.chat-panel').first();
    await chat.locator('.chat-form textarea').fill('保留原有草稿');
    const resultPromise = page.waitForResponse(response => response.url().endsWith('/api/chat/image/recognize'), { timeout: 180000 });
    await chat.locator('.image-picker input').setInputFiles(file);
    const response = await resultPromise;
    assert.equal(response.status(), 200);
    const result = (await response.json()).data;
    assert(result.text.includes('\\frac{x}{1+x}'));
    assert(result.text.includes('\\frac{f(x)}{x^{2}}'));
    const editor = chat.locator('.image-review textarea');
    await page.waitForFunction(() => document.querySelector('.image-review textarea')?.value.includes('\\frac{f(x)}{x^{2}}'));
    assert.equal(await editor.inputValue(), result.text);
    await page.screenshot({ path: path.join(out, 'real-image-recognition.png'), fullPage: true });
    await chat.getByRole('button', { name: '确认加入草稿', exact: true }).click();
    assert.equal(await chat.locator('.chat-form textarea').inputValue(), '保留原有草稿\n' + result.text.trim());
    assert.equal(paidRequests, 0);
    assert.equal(uploadRequests, 0);
    assert.deepEqual(errors, []);
    assert.equal(fs.readFileSync(path.join(data, 'budget.json'), 'utf8'), budget);
    fs.writeFileSync(path.join(out, 'browser-result.json'), JSON.stringify({
      recognized: result, original_image_actual_ocr: true, both_fractions_preserved: true,
      minus_variable_domain_limit_superscript_preserved: true, append_preserves_draft: true,
      paid_requests: paidRequests, document_upload_requests: uploadRequests, page_errors: errors,
    }, null, 2));
    console.log(JSON.stringify({ text: result.text, paid_requests: paidRequests, document_upload_requests: uploadRequests, page_errors: errors }, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
