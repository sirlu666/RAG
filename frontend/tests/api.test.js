import test from 'node:test'
import assert from 'node:assert/strict'
import { ApiError, requestApi, uploadDocument, replaceDocumentFile } from '../src/api.js'

function installXHR(t, reply) {
  const previous = globalThis.XMLHttpRequest
  let sent
  globalThis.XMLHttpRequest = class {
    upload = {}
    headers = {}
    open(method, path) { this.method = method; this.path = path }
    setRequestHeader(name, value) { this.headers[name] = value }
    send(body) { this.body = body; sent = this; reply(this) }
    abort() { this.onabort?.() }
  }
  t.after(() => {
    if (previous === undefined) delete globalThis.XMLHttpRequest
    else globalThis.XMLHttpRequest = previous
  })
  return () => sent
}

const file = () => new File(['数学例题'], 'math.txt', { type: 'text/plain' })

test('avatar FormData retains cookies and CSRF without overriding multipart boundary', async t => {
  let sent
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    sent = { path, ...options }
    return new Response(JSON.stringify({ code: 0, data: { user: { avatar_url: '/api/auth/me/avatar?v=new' } } }), { status: 200 })
  })
  const body = new FormData()
  body.append('file', new File(['image bytes'], 'avatar.png', { type: 'image/png' }))
  const result = await requestApi('/api/auth/me/avatar', { method: 'POST', body, csrfToken: 'csrf_example' })
  assert.equal(sent.path, '/api/auth/me/avatar')
  assert.equal(sent.body, body)
  assert.equal(sent.credentials, 'same-origin')
  assert.equal(sent.headers['X-CSRF-Token'], 'csrf_example')
  assert.equal(sent.headers['Content-Type'], undefined)
  assert.equal(result.user.avatar_url, '/api/auth/me/avatar?v=new')
})

test('replacement sends the fresh version to its document without using overwrite upload', async t => {
  const sent = installXHR(t, xhr => {
    xhr.status = 200
    xhr.responseText = JSON.stringify({ code: 0, data: { doc_id: 'doc_selected', changed: true } })
    xhr.onload()
  })
  const result = await replaceDocumentFile(file(), 'doc_selected', 'version_loaded', 'csrf_example')
  assert.equal(sent().path, '/api/docs/doc_selected/replacement')
  assert.equal(sent().body.get('version'), 'version_loaded')
  assert.equal(sent().body.get('overwrite'), null)
  assert.equal(sent().body.get('kb_id'), null)
  assert.equal(sent().headers['X-CSRF-Token'], 'csrf_example')
  assert.equal(sent().headers['Content-Type'], undefined)
  assert.equal(sent().timeout, 300000)
  assert.equal(result.changed, true)
})

test('multipart upload keeps target KB, CSRF and browser boundary; progress is transport-only', async t => {
  const percentages = []
  const sent = installXHR(t, xhr => {
    xhr.upload.onprogress({ lengthComputable: true, loaded: 5, total: 10 })
    xhr.status = 200
    xhr.responseText = JSON.stringify({ code: 0, data: { doc_id: 'doc_1', status: 'pending' } })
    xhr.onload()
  })
  const result = await uploadDocument(file(), 'kb_selected', 'csrf_example', { onProgress: n => percentages.push(n) })
  assert.equal(result.status, 'pending')
  assert.deepEqual(percentages, [50])
  assert.equal(sent().method, 'POST')
  assert.equal(sent().path, '/api/docs/upload')
  assert.equal(sent().withCredentials, true)
  assert.equal(sent().headers['X-CSRF-Token'], 'csrf_example')
  assert.equal(sent().headers['Content-Type'], undefined)
  assert.equal(sent().body.get('kb_id'), 'kb_selected')
  assert.equal(sent().body.get('overwrite'), 'false')
  assert.equal(sent().body.get('file').name, 'math.txt')
})

test('duplicate upload returns backend conflict instead of reporting success', async t => {
  installXHR(t, xhr => {
    xhr.status = 409
    xhr.responseText = JSON.stringify({ code: 1005, message: '文件已存在', data: null })
    xhr.onload()
  })
  await assert.rejects(uploadDocument(file(), 'kb_1', 'csrf'), err => err instanceof ApiError && err.status === 409 && err.message === '文件已存在')
})

test('timed-out upload tells caller to reconcile list before retrying', async t => {
  installXHR(t, xhr => xhr.ontimeout())
  await assert.rejects(uploadDocument(file(), 'kb_1', 'csrf'), err => err.status === 408 && err.message.includes('刷新列表'))
})

test('unmount cancellation aborts in-flight upload', async t => {
  const sent = installXHR(t, () => {})
  const controller = new AbortController()
  const result = uploadDocument(file(), 'kb_1', 'csrf', { signal: controller.signal })
  assert.ok(sent())
  controller.abort()
  await assert.rejects(result, err => err.status === -1)
})

test('already-cancelled uploads never send a file', async t => {
  const sent = installXHR(t, () => assert.fail('Unexpected file upload'))
  const controller = new AbortController()
  controller.abort()
  await assert.rejects(uploadDocument(file(), 'kb_1', 'csrf', { signal: controller.signal }), err => err.status === -1)
  assert.equal(sent(), undefined)
})

test('JSON requests retain cookies and CSRF after cancellation support is added', async t => {
  t.mock.method(globalThis, 'fetch', async (path, options) => {
    assert.equal(path, '/api/kbs')
    assert.equal(options.credentials, 'same-origin')
    assert.equal(options.headers['X-CSRF-Token'], 'csrf')
    assert.equal(options.headers['Content-Type'], 'application/json')
    assert.deepEqual(JSON.parse(options.body), { name: '高等数学' })
    return Response.json({ code: 0, data: { id: 'kb_1' } })
  })
  assert.deepEqual(await requestApi('/api/kbs', { method: 'POST', body: { name: '高等数学' }, csrfToken: 'csrf' }), { id: 'kb_1' })
})

test('cancelled polling is distinguishable from a connectivity error', async t => {
  t.mock.method(globalThis, 'fetch', async (_path, options) => {
    assert.equal(options.signal.aborted, true)
    throw new DOMException('Aborted', 'AbortError')
  })
  const controller = new AbortController()
  controller.abort()
  await assert.rejects(requestApi('/api/docs/doc_old/status', { signal: controller.signal }), err => err.status === -1)
})
