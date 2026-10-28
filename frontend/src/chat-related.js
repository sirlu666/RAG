export function normalizeRelated(data = {}) {
  return {
    questions: [...new Set((Array.isArray(data.related_questions) ? data.related_questions : [])
      .filter(text => typeof text === 'string' && text.trim() && text.length <= 2000))],
    materials: (Array.isArray(data.related_materials) ? data.related_materials : [])
      .filter(item => item && typeof item.doc_id === 'string' && typeof item.chunk_id === 'string'
        && item.doc_id && item.chunk_id),
  }
}
