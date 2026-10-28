// Queue IDs and photo filenames only; these are not authentication tokens.
export function newUploadId() {
  if (typeof globalThis.crypto?.randomUUID === 'function') return globalThis.crypto.randomUUID()
  const bytes = new Uint8Array(16)
  globalThis.crypto.getRandomValues(bytes)
  return Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
}

export function fileProblem(file) {
  if (!/\.(pdf|docx|md|txt|png|jpe?g)$/i.test(file.name)) return '仅支持 PDF、DOCX、MD、TXT、PNG、JPG、JPEG。'
  if (!file.size || file.size > 50 * 1024 * 1024) return '文件不能为空，单文件最多 50MB。'
  return ''
}

// A failure belongs to its file. Authentication loss or cancellation ends the batch.
export async function runUploadQueue(entries, send, { signal, onAccepted, onError } = {}) {
  for (const entry of entries) {
    if (signal?.aborted) break
    if (entry.status !== 'queued') continue
    entry.status = 'uploading'
    try {
      const result = await send(entry.file, percent => { entry.percent = percent })
      entry.docId = result.doc_id
      entry.percent = 100
      entry.status = 'accepted'
    } catch (cause) {
      entry.status = cause.status === -1 ? 'cancelled' : 'failed'
      entry.error = cause.message
      onError?.(cause)
      if (cause.status === 401 || cause.status === -1) break
      continue
    }
    // List refresh errors must not relabel an accepted upload as failed.
    await onAccepted?.(entry)
  }
}
