// Uses the existing local Playwright runtime. All OCR/chat/history responses are fixtures.
const { chromium } = require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const base = 'http://localhost:5174';
  const data = path.join(process.env.LOCALAPPDATA, 'Temp/mathrag-c-integration-20261028');
  const out = path.resolve(__dirname, '../.tmp/chat-ui-review');
  fs.mkdirSync(out, { recursive: true });
  const budgetBefore = fs.readFileSync(path.join(data, 'budget.json'), 'utf8');
  const account = JSON.parse(fs.readFileSync(path.join(data, 'browser-account.json'), 'utf8'));
  const browser = await chromium.launch({ headless: true, executablePath: path.join(process.env.LOCALAPPDATA,
    'ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-win64/chrome-headless-shell.exe') });
  try {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    let streamCount = 0, ocrMode = 'success', streamMode = 'done', lastQuestion, heldRoute;
    const errors = [];
    const related = { related_questions: ['如何验证这个答案？'], related_materials: [
      { doc_id: 'fixture-doc', chunk_id: 'fixture-chunk', doc_name: '测试资料.txt', seq: 6, page: 2 },
    ] };
    const ok = (route, data) => route.fulfill({ json: { code: 0, data } });
    // Single boundary prevents all unexpected mutation / model calls.
    await context.route('**/api/**', async route => {
      const req = route.request(), url = new URL(req.url());
      if (/\/chat\/stream$/.test(url.pathname)) {
        streamCount++;
        lastQuestion = req.postDataJSON().question;
        const done = { answer: '测试回答', ...related, ...(streamMode === 'refused' ? { refused: true } : {}) };
        const frame = (event, data) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
        return route.fulfill({ contentType: 'text/event-stream', body: frame('meta', { conversation_id: 'fixture-session' })
          + frame('delta', { text: '测试回答' }) + (streamMode === 'failed'
            ? frame('error', { message: '测试中断' }) : frame('done', done)) });
      }
      if (url.pathname === '/api/chat/image/recognize') {
        assert(req.headers()['x-csrf-token']);
        if (ocrMode === 'hold') { heldRoute = route; return; }
        if (ocrMode === 'fail' || ocrMode === 'expired') return route.fulfill({ status: ocrMode === 'expired' ? 401 : 400,
          json: { code: 1001, message: ocrMode === 'expired' ? '测试登录失效' : '测试识别失败' } });
        return ok(route, { text: '解方程 x+1=2', latex: '', warnings: ['请校对公式'] });
      }
      if (url.pathname === '/api/public/kbs') return ok(route, [{ id: 'public-fixture', name: '游客测试资料' }]);
      if (url.pathname === '/api/conversations') return ok(route, { items: [
        { id: 'fixture-session', title: '推荐历史测试', kb_ids: [context.kbId] },
      ], total: 1 });
      if (url.pathname === '/api/conversations/fixture-session/messages') return ok(route, {
        conversation: { id: 'fixture-session', kb_ids: [context.kbId] }, has_more: false,
        items: [{ id: 'u', role: 'user', content: '历史问题' },
          { id: 'a', role: 'assistant', content: '测试回答', status: 'done', ...related }],
      });
      if (url.pathname === '/api/docs/fixture-doc/preview') {
        assert.equal(url.searchParams.get('page'), '2');
        return ok(route, { items: [{ id: 'fixture-chunk', seq: 6, page: 2, content: '测试定位正文' }] });
      }
      if (req.method() !== 'GET' && url.pathname !== '/api/auth/login') throw new Error(`Unexpected mutation: ${url.pathname}`);
      return route.continue();
    });
    const login = await context.request.post(base + '/api/auth/login', {
      data: account, headers: { Origin: base },
    });
    assert.equal(login.status(), 200);
    const page = await context.newPage();
    await page.addInitScript(() => {
      const create = URL.createObjectURL.bind(URL), revoke = URL.revokeObjectURL.bind(URL);
      window.activeBlobUrls = new Set();
      URL.createObjectURL = blob => { const url = create(blob); window.activeBlobUrls.add(url); return url; };
      URL.revokeObjectURL = url => { window.activeBlobUrls.delete(url); revoke(url); };
    });
    page.on('pageerror', e => errors.push(e.message));
    await page.goto(base);
    await page.getByRole('button', { name: '资料：数学真实联调资料', exact: true }).click();
    const chat = page.locator('.chat-panel').first();
    await chat.waitFor();
    // Discover selected KB from the normal list request; no data changes.
    const kbs = (await (await context.request.get(base + '/api/kbs')).json()).data;
    context.kbId = kbs.find(kb => kb.name === '数学真实联调资料').id;
    const question = chat.locator('.chat-form textarea');
    const input = chat.locator('.image-picker input');
    const image = { name: 'question.png', mimeType: 'image/png', buffer: Buffer.from(
      'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII=', 'base64') };
    await question.fill('原有草稿');
    await input.setInputFiles(image);
    await chat.getByText('请校对公式', { exact: true }).waitFor();
    await chat.locator('.image-review textarea').fill('校对后的题目 x=1');
    await chat.getByRole('button', { name: '确认加入草稿' }).click();
    assert.equal(await question.inputValue(), '原有草稿\n校对后的题目 x=1');
    assert.equal(streamCount, 0);
    // Length guard must preserve the OCR editor and the existing draft.
    await question.fill('原'.repeat(1999));
    await input.setInputFiles(image);
    await chat.getByRole('button', { name: '确认加入草稿' }).click();
    await chat.getByText('加入后超过 2000 字，请缩短草稿或识别文本。').waitFor();
    assert.equal(await question.inputValue(), '原'.repeat(1999));
    await chat.getByRole('button', { name: '取消图片' }).click();
    ocrMode = 'fail';
    await input.setInputFiles(image);
    await chat.getByText('测试识别失败', { exact: true }).waitFor();
    ocrMode = 'success';
    await chat.getByRole('button', { name: '重新识别' }).click();
    await chat.getByText('请校对公式', { exact: true }).waitFor();
    await chat.getByRole('button', { name: '取消图片' }).click();
    ocrMode = 'hold';
    await input.setInputFiles(image);
    await page.waitForFunction(() => document.querySelector('.image-question[aria-busy="true"]'));
    await chat.getByRole('button', { name: '取消图片' }).click();
    if (heldRoute) await heldRoute.fulfill({ json: { code: 0, data: { text: '过期结果' } } }).catch(() => {});
    assert.equal(await chat.locator('.image-review').count(), 0);
    assert.equal(streamCount, 0);
    await question.fill('发送测试题');
    await chat.getByRole('button', { name: '发送问题' }).click();
    await chat.locator('.related-panel').waitFor();
    assert.equal(lastQuestion, '发送测试题');
    await chat.getByRole('button', { name: '如何验证这个答案？' }).click();
    assert.equal(await question.inputValue(), '如何验证这个答案？');
    assert.equal(streamCount, 1);
    await chat.getByRole('button', { name: /测试资料.txt/ }).click();
    await chat.getByText('测试定位正文', { exact: true }).waitFor();
    await chat.getByRole('button', { name: '推荐历史测试', exact: true }).click();
    await chat.getByText('历史问题', { exact: true }).waitFor();
    assert.equal(await chat.locator('.related-panel').count(), 1);
    await page.screenshot({ path: path.join(out, 'recommendations.png'), fullPage: true });
    for (const mode of ['refused', 'failed']) {
      await chat.getByRole('button', { name: '新对话', exact: true }).click();
      streamMode = mode;
      await question.fill('测试拒答或失败');
      await chat.getByRole('button', { name: '发送问题' }).click();
      await chat.getByRole('button', { name: '发送问题' }).waitFor();
      assert.equal(await chat.locator('.related-panel').count(), 0);
    }
    ocrMode = 'success';
    await input.setInputFiles(image);
    await chat.getByText('请校对公式', { exact: true }).waitFor();
    await page.screenshot({ path: path.join(out, 'image-review.png'), fullPage: true });
    await chat.getByRole('button', { name: '取消图片' }).click();
    ocrMode = 'expired';
    await input.setInputFiles(image);
    await page.getByText('登录已过期，请重新登录。', { exact: true }).waitFor();
    assert.equal(await page.evaluate(() => window.activeBlobUrls.size), 0);
    await page.getByRole('button', { name: '知识库与问答', exact: true }).click();
    await page.getByRole('button', { name: '游客测试资料', exact: true }).click();
    await page.getByText('登录后可使用图片识题。', { exact: true }).waitFor();
    assert.equal(await page.locator('.image-picker').count(), 0);
    assert.deepEqual(errors, []);
    assert.equal(fs.readFileSync(path.join(data, 'budget.json'), 'utf8'), budgetBefore);
    fs.writeFileSync(path.join(out, 'result.json'), JSON.stringify({
      image_edit_append_cancel_retry_length_guard_expiry_guest_blob_cleanup: true,
      live_history_recommendations_source_navigation: true,
      refused_failed_hide_recommendations: true, page_errors: errors,
      fixture_stream_requests: streamCount, paid_model_calls: 0,
      note: 'Browser OCR/chat/history/preview use fixtures; real backend API verified by pytest.',
    }, null, 2));
    console.log(fs.readFileSync(path.join(out, 'result.json'), 'utf8'));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
