/**
 * SSE 客户端 —— 事件协议见 docs/01-架构与接口契约.md §6
 *
 * 为什么不用 EventSource：它不支持 POST、不能带 Authorization 头。
 * 所以用 fetch + ReadableStream 手动按 \n\n 分帧。
 */

export interface Citation {
  index: number
  chunk_id: string
  doc_name: string
  page?: number
  snippet: string
  score: number
  content_type?: string
}

export interface ChatStreamHandlers {
  onMeta?: (d: { message_id: string; conversation_id: string; retrieval_ms: number; hits: number }) => void
  onCitation?: (d: Citation) => void
  onDelta?: (text: string) => void
  onDone?: (d: { message_id: string; tokens_in: number; tokens_out: number; latency_ms: number; confidence: number }) => void
  onError?: (e: { code: number; message: string }) => void
}

export interface ChatStreamParams {
  conversation_id?: string | null
  kb_ids: string[]
  question: string
}

function getToken(): string {
  return localStorage.getItem('token') ?? ''
}

/**
 * 发起一次流式问答。
 * @returns 完整的回答文本（便于落库/复制）
 */
export async function streamChat(
  params: ChatStreamParams,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<string> {
  const res = await fetch('/api/chat/stream', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ ...params, stream: true }),
    signal,
  })

  if (!res.ok || !res.body) {
    const msg = res.status === 401 ? '登录已过期，请重新登录' : `请求失败（HTTP ${res.status}）`
    handlers.onError?.({ code: res.status === 401 ? 1002 : 5000, message: msg })
    return ''
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''
  let answer = ''

  const dispatch = (frame: string) => {
    let event = 'message'
    const dataLines: string[] = []
    for (const line of frame.split('\n')) {
      if (line.startsWith('event:')) event = line.slice(6).trim()
      else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
      else if (line.startsWith(':')) continue // 心跳注释
    }
    if (!dataLines.length) return

    let payload: any
    try {
      payload = JSON.parse(dataLines.join('\n'))
    } catch {
      return // 半包/脏包直接丢弃，不要炸掉整个渲染
    }

    switch (event) {
      case 'meta':
        handlers.onMeta?.(payload)
        break
      case 'citation':
        handlers.onCitation?.(payload)
        break
      case 'delta':
        answer += payload.text ?? ''
        handlers.onDelta?.(payload.text ?? '')
        break
      case 'done':
        handlers.onDone?.(payload)
        break
      case 'error':
        handlers.onError?.(payload)
        break
    }
  }

  try {
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })

      let idx = buffer.indexOf('\n\n')
      while (idx >= 0) {
        dispatch(buffer.slice(0, idx))
        buffer = buffer.slice(idx + 2)
        idx = buffer.indexOf('\n\n')
      }
    }
    if (buffer.trim()) dispatch(buffer) // 收尾残帧
  } catch (e: any) {
    if (e?.name !== 'AbortError') {
      handlers.onError?.({ code: 4001, message: '连接中断，请重试' })
    }
  }

  return answer
}
