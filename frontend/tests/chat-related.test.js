import test from 'node:test'
import assert from 'node:assert/strict'
import { normalizeRelated } from '../src/chat-related.js'
import { messagesToTurns } from '../src/chat-history.js'

test('related metadata rejects malformed entries and retains source coordinates', () => {
  const material = { doc_id: 'd1', chunk_id: 'c1', seq: 9, page: 3 }
  assert.deepEqual(normalizeRelated({ related_questions: ['求根', null, '', '求根', 'x'.repeat(2001)],
    related_materials: [null, {}, material] }), { questions: ['求根'], materials: [material] })
  assert.deepEqual(normalizeRelated({ related_questions: {}, related_materials: 'bad' }), { questions: [], materials: [] })
})

test('history restores the same recommendations as a live done event and supports old messages', () => {
  const data = { related_questions: ['为什么？'], related_materials: [{ doc_id: 'd', chunk_id: 'c' }] }
  const turn = messagesToTurns([{ id: 'a', role: 'assistant', content: '答案', status: 'done', ...data }])[0]
  assert.deepEqual(turn.related, normalizeRelated(data))
  assert.deepEqual(messagesToTurns([{ id: 'b', role: 'assistant', content: '旧答案' }])[0].related,
    { questions: [], materials: [] })
})
