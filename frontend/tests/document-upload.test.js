import test from 'node:test'
import assert from 'node:assert/strict'
import { fileProblem, newUploadId, runUploadQueue } from '../src/document-upload.js'

test('photo IDs work when randomUUID is unavailable on LAN HTTP', t => {
  const original = Object.getOwnPropertyDescriptor(globalThis.crypto, 'randomUUID')
  Object.defineProperty(globalThis.crypto, 'randomUUID', { configurable: true, value: undefined })
  t.after(() => {
    if (original) Object.defineProperty(globalThis.crypto, 'randomUUID', original)
    else delete globalThis.crypto.randomUUID
  })
  const first = newUploadId()
  const second = newUploadId()
  assert.match(first, /^[a-f0-9]{32}$/)
  assert.notEqual(first, second)
})

const entry = name => ({ file: { name, size: 100 }, status: 'queued', percent: 0 })

test('rejects unsupported, empty and oversized files before sending', () => {
  assert.equal(fileProblem({ name: '数学.MD', size: 100 }), '')
  for (const file of [{ name: 'a.exe', size: 100 }, { name: 'a.txt', size: 0 }, { name: 'a.pdf', size: 50 * 1024 * 1024 + 1 }]) {
    assert.ok(fileProblem(file))
  }
})

test('batch uploads serially and continues after an individual failure', async () => {
  const items = [entry('1.txt'), entry('2.md'), entry('3.pdf')]
  let active = 0
  const accepted = []
  await runUploadQueue(items, async (file, progress) => {
    assert.equal(++active, 1)
    await Promise.resolve()
    progress(70)
    active--
    if (file.name === '2.md') throw Object.assign(new Error('网络中断，请核对列表'), { status: 0 })
    return { doc_id: file.name }
  }, { onAccepted: item => { accepted.push(item.docId) } })
  assert.deepEqual(items.map(item => item.status), ['accepted', 'failed', 'accepted'])
  assert.deepEqual(accepted, ['1.txt', '3.pdf'])
  assert.equal(items[0].percent, 100)
  assert.match(items[1].error, /核对列表/)
})

test('session expiration stops remaining uploads and accepted items are not resent', async () => {
  const items = [entry('1.txt'), entry('2.txt'), entry('3.txt')]
  items[0].status = 'accepted'
  const sent = []
  await runUploadQueue(items, async file => {
    sent.push(file.name)
    throw Object.assign(new Error('请重新登录'), { status: 401 })
  })
  assert.deepEqual(sent, ['2.txt'])
  assert.equal(items[2].status, 'queued')
})

test('leaving the page stops the queue without starting another file', async () => {
  const controller = new AbortController()
  const items = [entry('1.txt'), entry('2.txt')]
  await runUploadQueue(items, async () => {
    controller.abort()
    throw Object.assign(new Error('请求已取消'), { status: -1 })
  }, { signal: controller.signal })
  assert.deepEqual(items.map(item => item.status), ['cancelled', 'queued'])
})
