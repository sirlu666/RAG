// Real Nginx + real bounded backend. No question is sent to a model.
const { chromium } = require('C:/Users/Lenovo/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

(async () => {
  const base = 'http://localhost:8086';
  const data = path.join(process.env.LOCALAPPDATA, 'Temp/mathrag-c-integration-20261028');
  const out = path.join(data, 'nginx-restart-20261028');
  const expected = JSON.parse(fs.readFileSync(path.join(out, 'expected-history-related.json'), 'utf8'));
  const account = JSON.parse(fs.readFileSync(path.join(data, 'browser-account.json'), 'utf8'));
  const budget = fs.readFileSync(path.join(data, 'budget.json'), 'utf8');
  const browser = await chromium.launch({ headless: true, executablePath: path.join(process.env.LOCALAPPDATA,
    'ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-win64/chrome-headless-shell.exe') });
  try {
    const guest = await browser.newContext();
    assert.equal((await guest.request.get(base + '/api/conversations')).status(), 401);
    await guest.close();
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } });
    await context.route(/\/api\/(?:public\/)?chat\/stream/, route => route.abort());
    const auth = await context.request.post(base + '/api/auth/login', { data: account, headers: { Origin: base } });
    assert.equal(auth.status(), 200);
    const session = (await auth.json()).data;
    const kbs = (await (await context.request.get(base + '/api/kbs')).json()).data;
    const kb = kbs.find(row => row.name === '数学真实联调资料');
    const history = (await (await context.request.get(base + '/api/conversations?kb_id=' + kb.id)).json()).data.items;
    let inspected = 0, withRelated = 0, selected;
    for (const conversation of history) {
      const response = await context.request.get(base + '/api/conversations/' + conversation.id + '/messages');
      assert.equal(response.status(), 200);
      for (const message of (await response.json()).data.items) {
        assert(Array.isArray(message.related_questions));
        assert(Array.isArray(message.related_materials));
        if (expected[message.id]) {
          assert.deepEqual(message.related_questions, expected[message.id].related_questions);
          assert.deepEqual(message.related_materials, expected[message.id].related_materials);
          inspected++;
          if ((message.related_questions.length || message.related_materials.length) && message.status === 'done'
            && !message.refused && !message.declined) { withRelated++; selected = conversation; }
        }
      }
    }
    assert(inspected > 0 && withRelated > 0);
    // Invalid write fails at the CSRF boundary, before title validation or mutation.
    const denied = await context.request.patch(base + '/api/conversations/' + history[0].id,
      { data: { title: 'should-never-be-written' }, headers: { Origin: base } });
    assert.equal(denied.status(), 403);
    const page = await context.newPage();
    const errors = []; page.on('pageerror', e => errors.push(e.message));
    await page.goto(base);
    await page.getByRole('button', { name: '资料：数学真实联调资料', exact: true }).click();
    const chat = page.locator('.chat-panel').first();
    await chat.getByRole('button', { name: selected.title, exact: true }).first().click();
    await chat.locator('.related-panel').first().waitFor();
    await page.screenshot({ path: path.join(out, 'nginx-real-history.png'), fullPage: true });
    assert.deepEqual(errors, []);
    assert.equal(fs.readFileSync(path.join(data, 'budget.json'), 'utf8'), budget);
    const result = { nginx_login_cookie: true, anonymous_history_401: true, missing_csrf_write_403: true,
      assistant_history_records_matched_database: inspected, completed_records_with_related: withRelated,
      real_saved_recommendations_rendered: true, csrf_token_present: !!session.csrf_token,
      page_errors: errors, paid_model_calls: 0 };
    fs.writeFileSync(path.join(out, 'history-ui-result.json'), JSON.stringify(result, null, 2));
    console.log(JSON.stringify(result, null, 2));
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
