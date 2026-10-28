export class ApiError extends Error {
  constructor(message, status) {
    super(message)
    this.status = status
  }
}

export async function requestApi(path, { method = 'GET', body, csrfToken, signal, timeoutMs = 15000 } = {}) {
  const multipart = typeof FormData !== 'undefined' && body instanceof FormData
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(path, {
      method,
      credentials: 'same-origin',
      signal: signal ? AbortSignal.any([controller.signal, signal]) : controller.signal,
      headers: {
        ...(body === undefined || multipart ? {} : { 'Content-Type': 'application/json' }),
        ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {}),
      },
      ...(body === undefined ? {} : { body: multipart ? body : JSON.stringify(body) }),
    })
    const payload = await response.json().catch(() => null)
    if (response.status === 404 && path.startsWith('/api/auth/')) {
      throw new ApiError('后端尚未载入账号接口，请停止并重新启动后端，再点“重新连接”。', 404)
    }
    if (response.status === 404 && path === '/api/kbs') {
      throw new ApiError('后端尚未载入知识库接口，请重新启动后端，再点“刷新列表”。', 404)
    }
    if (!response.ok || payload?.code !== 0) {
      throw new ApiError(payload?.message || '服务暂时不可用，请稍后重试。', response.status)
    }
    return payload.data
  } catch (error) {
    if (signal?.aborted) throw new ApiError('请求已取消。', -1)
    if (error instanceof ApiError) throw error
    throw new ApiError(error.name === 'AbortError' ? '请求超时，请检查连接后重试。' : '无法连接后端，请确认服务已启动。', 0)
  } finally {
    clearTimeout(timeout)
  }
}

export function uploadDocument(file, kbId, csrfToken, options = {}) {
  return sendDocument(file, '/api/docs/upload', csrfToken, { kb_id: kbId, overwrite: 'false' }, options)
}

export function replaceDocumentFile(file, docId, version, csrfToken, options = {}) {
  return sendDocument(file, `/api/docs/${encodeURIComponent(docId)}/replacement`, csrfToken, { version }, { timeoutMs: 300000, ...options })
}

export function recognizeDocumentFormula(file, docId, version, csrfToken, options = {}) {
  return sendDocument(file, `/api/docs/${encodeURIComponent(docId)}/formula`, csrfToken, { version }, { timeoutMs: 180000, ...options })
}

function sendDocument(file, path, csrfToken, fields, { onProgress, signal, timeoutMs = 120000 } = {}) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    const abort = () => xhr.abort()
    const finish = (callback, value) => {
      signal?.removeEventListener('abort', abort)
      callback(value)
    }
    if (signal?.aborted) {
      reject(new ApiError('请求已取消。', -1))
      return
    }
    xhr.open('POST', path)
    xhr.withCredentials = true
    xhr.timeout = timeoutMs
    xhr.setRequestHeader('X-CSRF-Token', csrfToken)
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) {
        onProgress?.(Math.min(100, Math.round(event.loaded / event.total * 100)))
      }
    }
    xhr.onload = () => {
      let payload
      try { payload = JSON.parse(xhr.responseText) } catch { /* Use a readable error below. */ }
      if (xhr.status >= 200 && xhr.status < 300 && payload?.code === 0 && payload.data?.doc_id) {
        finish(resolve, payload.data)
      } else {
        finish(reject, new ApiError(payload?.message || '上传未成功，请刷新文档列表确认后再重试。', xhr.status))
      }
    }
    xhr.onerror = () => finish(reject, new ApiError('上传连接中断，请先刷新列表确认是否已受理，避免重复上传。', 0))
    xhr.ontimeout = () => finish(reject, new ApiError('上传超时，请先刷新列表确认是否已受理，避免重复上传。', 408))
    xhr.onabort = () => finish(reject, new ApiError('请求已取消。', -1))
    signal?.addEventListener('abort', abort, { once: true })
    const form = new FormData()
    form.append('file', file)
    for (const [key, value] of Object.entries(fields)) form.append(key, value)
    // Browser supplies the multipart boundary; never set Content-Type manually.
    xhr.send(form)
  })
}
