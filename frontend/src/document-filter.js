export function hasAutoTags(doc) {
  return Boolean(doc.knowledge_points?.length || doc.question_types?.length || doc.difficulty)
}

export function filterDocuments(documents, query = '', category = null, {
  knowledgePoint = null, questionType = null, difficulty = null, tagStatus = 'all',
} = {}) {
  const needle = query.trim().toLocaleLowerCase()
  return documents.filter(doc =>
    (!needle || doc.filename.toLocaleLowerCase().includes(needle)) &&
    (category === null || (doc.category || '') === category) &&
    (knowledgePoint === null || (doc.knowledge_points || []).includes(knowledgePoint)) &&
    (questionType === null || (doc.question_types || []).includes(questionType)) &&
    (difficulty === null || doc.difficulty === difficulty) &&
    (tagStatus === 'all' || hasAutoTags(doc) === (tagStatus === 'tagged')))
}
