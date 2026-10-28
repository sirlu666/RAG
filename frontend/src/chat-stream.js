import { ApiError } from './api.js'

const events = new Set(['meta', 'citation', 'delta', 'done', 'error'])

// CRLF, multiline data, comments and partial network frames are handled here.
export function createSSEParser(onEvent) {
  let buffer = ''
  let event = 'message'
  let data = []
  function line(value) {
    if (!value) {
      if (data.length && events.has(event)) {
        let payload
        try { payload = JSON.parse(data.join('\n')) } catch { throw new ApiError('回答事件格式不正确，请重新提问。', 502) }
        onEvent(event, payload)
      }
      event = 'message'
      data = []
      return
    }
    if (value.startsWith(':')) return
    const colon = value.indexOf(':')
    const field = colon < 0 ? value : value.slice(0, colon)
    const content = colon < 0 ? '' : value.slice(colon + 1).replace(/^ /, '')
    if (field === 'event') event = content
    if (field === 'data') data.push(content)
  }
  return {
    push(text, final = false) {
      buffer += text
      while (true) {
        const index = buffer.search(/[\r\n]/)
        if (index < 0 || (!final && index === buffer.length - 1 && buffer[index] === '\r')) break
        const size = buffer[index] === '\r' && buffer[index + 1] === '\n' ? 2 : 1
        const value = buffer.slice(0, index)
        buffer = buffer.slice(index + size)
        line(value)
      }
      if (final) {
        if (buffer) line(buffer)
        buffer = ''
        line('')
      }
    },
  }
}

export async function streamChat(body, csrfToken, { signal, onEvent, publicOnly = false } = {}) {
  const controller = new AbortController()
  let idleTimer
  const resetIdle = () => {
    clearTimeout(idleTimer)
    idleTimer = setTimeout(() => controller.abort(), 120000)
  }
  const totalTimer = setTimeout(() => controller.abort(), 300000)
  let reader
  let done = false
  resetIdle()
  try {
    const response = await fetch(publicOnly ? '/api/public/chat/stream' : '/api/chat/stream', {
      method: 'POST', credentials: 'same-origin',
      signal: signal ? AbortSignal.any([signal, controller.signal]) : controller.signal,
      headers: { 'Content-Type': 'application/json', 'Accept': 'text/event-stream', ...(!publicOnly ? { 'X-CSRF-Token': csrfToken } : {}) },
      body: JSON.stringify({ ...body, stream: true }),
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => null)
      throw new ApiError(payload?.message || '问答请求失败，请稍后重试。', response.status)
    }
    if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
      throw new ApiError('服务器未返回流式回答，请检查后端连接。', 502)
    }
    const parser = createSSEParser((event, data) => {
      if (done) return
      if (!data || typeof data !== 'object') throw new ApiError('回答事件数据不正确。', 502)
      if (event === 'error') throw new ApiError(data.message || '生成中断，请稍后重试。', 502)
      if (event === 'delta' && typeof data.text !== 'string') throw new ApiError('回答文本格式不正确。', 502)
      if (event === 'meta' && typeof data.conversation_id !== 'string') throw new ApiError('会话信息不正确。', 502)
      if (event === 'done') done = true
      onEvent?.(event, data)
    })
    reader = response.body.getReader()
    const decoder = new TextDecoder()
    while (!done) {
      const chunk = await reader.read()
      if (chunk.done) {
        parser.push(decoder.decode(), true)
        break
      }
      resetIdle()
      parser.push(decoder.decode(chunk.value, { stream: true }))
    }
    if (!done) throw new ApiError('连接已结束，但未收到回答完成信号；已收到的内容仅为部分回答。', 502)
  } catch (cause) {
    if (signal?.aborted) throw new ApiError('已停止接收回答。', -1)
    if (cause instanceof ApiError) throw cause
    throw new ApiError(cause.name === 'AbortError' ? '回答等待超时，已保留收到的内容。' : '回答连接中断，已保留收到的内容。', 0)
  } finally {
    clearTimeout(idleTimer)
    clearTimeout(totalTimer)
    if (reader) {
      await reader.cancel().catch(() => {})
      reader.releaseLock()
    }
  }
}
