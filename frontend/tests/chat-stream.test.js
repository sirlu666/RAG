import test from 'node:test'
import assert from 'node:assert/strict'
import { createSSEParser, streamChat } from '../src/chat-stream.js'

const frame = (event, data) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
function response(text, byteByByte = false) {
  const bytes = new TextEncoder().encode(text)
  return new Response(new ReadableStream({
    start(controller) {
      if (byteByByte) for (const byte of bytes) controller.enqueue(new Uint8Array([byte]))
      else controller.enqueue(bytes)
      controller.close()
    },
  }), { headers: { 'Content-Type': 'text/event-stream; charset=utf-8' } })
}

test('parser handles CRLF split across pushes, comments and multiline JSON', () => {
  const events = []
  const parser = createSSEParser((event, data) => events.push([event, data]))
  parser.push(': ping\r')
  parser.push('\nevent: delta\r\ndata: {\r\ndata: "text": "中文"}\r')
  assert.equal(events.length, 0)
  parser.push('\n\r\n')
  assert.deepEqual(events, [['delta', { text: '中文' }]])
})

test('guest streaming uses the public endpoint without a CSRF token or saved conversation id', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/public/chat/stream')
    assert.equal(options.headers['X-CSRF-Token'], undefined)
    assert.deepEqual(JSON.parse(options.body), { kb_ids: ['kb_public'], question: '求根', stream: true })
    return response(frame('meta', { conversation_id: 'guest_1' }) + frame('done', { answer: '解答', citations: [], guest: true }))
  })
  const events = []
  await streamChat({ kb_ids: ['kb_public'], question: '求根' }, '', { publicOnly: true, onEvent: (event, data) => events.push([event, data]) })
  assert.equal(events.at(-1)[1].guest, true)
})

test('stream preserves UTF-8 split by byte, sends Cookie and CSRF, receives canonical done', async t => {
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/chat/stream')
    assert.equal(options.credentials, 'same-origin')
    assert.equal(options.headers['X-CSRF-Token'], 'csrf_example')
    assert.deepEqual(JSON.parse(options.body), { kb_ids: ['kb_1'], question: '求根', stream: true })
    return response(frame('meta', { conversation_id: 'c_1' }) + frame('delta', { text: '由题意，[9]' }) + frame('done', { answer: '由题意，[1]', refused: false }), true)
  })
  const events = []
  await streamChat({ kb_ids: ['kb_1'], question: '求根' }, 'csrf_example', { onEvent: (event, data) => events.push([event, data]) })
  assert.equal(events[1][1].text, '由题意，[9]')
  assert.equal(events.at(-1)[1].answer, '由题意，[1]')
})

test('EOF without done is an interrupted answer', async t => {
  t.mock.method(globalThis, 'fetch', async () => response(frame('delta', { text: '部分答案' })))
  await assert.rejects(streamChat({}, 'csrf'), error => error.message.includes('未收到回答完成信号'))
})

test('HTTP auth error is not parsed as SSE', async t => {
  t.mock.method(globalThis, 'fetch', async () => Response.json({ code: 1002, message: '请先登录' }, { status: 401 }))
  await assert.rejects(streamChat({}, 'csrf'), error => error.status === 401 && error.message === '请先登录')
})

test('SSE errors preserve preceding partial text and reject', async t => {
  t.mock.method(globalThis, 'fetch', async () => response(frame('delta', { text: '部分' }) + frame('error', { message: '模型不可用' })))
  let partial = ''
  await assert.rejects(streamChat({}, 'csrf', { onEvent: (_event, data) => { partial += data.text || '' } }), /模型不可用/)
  assert.equal(partial, '部分')
})

test('manual stop aborts a waiting stream', async t => {
  const controller = new AbortController()
  t.mock.method(globalThis, 'fetch', async (_url, options) => new Response(new ReadableStream({
    start(stream) {
      options.signal.addEventListener('abort', () => stream.error(new DOMException('Aborted', 'AbortError')), { once: true })
    },
  }), { headers: { 'Content-Type': 'text/event-stream' } }))
  const pending = streamChat({}, 'csrf', { signal: controller.signal })
  await Promise.resolve()
  controller.abort()
  await assert.rejects(pending, error => error.status === -1)
})

test('malformed JSON and unexpected content type fail explicitly', async t => {
  t.mock.method(globalThis, 'fetch', async () => response('event: delta\ndata: bad-json\n\n'))
  await assert.rejects(streamChat({}, 'csrf'), /格式不正确/)
  t.mock.method(globalThis, 'fetch', async () => Response.json({ code: 0 }))
  await assert.rejects(streamChat({}, 'csrf'), /未返回流式回答/)
})
