// Rebuild visible turns from chronological message pages, without guessing that
// legacy or unanswered records are completed answers.
export function messagesToTurns(messages) {
  const turns = []
  for (const message of messages) {
    if (message.role === 'user') {
      turns.push({ id: `saved-${message.id}`, question: message.content, answer: '', citations: [],
        status: 'unanswered', info: null, error: '', model: null })
    } else if (message.role === 'assistant') {
      let turn = turns.at(-1)
      if (!turn || turn.status !== 'unanswered') {
        turn = { id: `saved-${message.id}`, question: '', answer: '', citations: [], status: 'unanswered', error: '' }
        turns.push(turn)
      }
      const noEvidence = message.refused || message.declined || message.content.trimStart().startsWith('未找到依据')
      turn.answer = message.content
      turn.model = message.model
      turn.status = noEvidence ? 'no-evidence' : ['done', 'failed', 'stopped'].includes(message.status) ? message.status : 'legacy'
      turn.citations = noEvidence ? [] : (message.citations || [])
      turn.error = message.status === 'failed' ? '此历史回答生成失败，内容可能不完整。' : message.status === 'stopped' ? '此历史回答未完整生成。' : ''
    }
  }
  return turns
}
