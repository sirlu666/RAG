import test from 'node:test'
import assert from 'node:assert/strict'
import { messagesToTurns } from '../src/chat-history.js'

test('restores questions, answers, citations and recorded mock mode', () => {
  const result = messagesToTurns([
    { id: 'u1', role: 'user', content: '求根' },
    { id: 'a1', role: 'assistant', content: '$x=1$', citations: [{ index: 1 }], model: 'mock', status: 'done' },
  ])
  assert.equal(result[0].question, '求根')
  assert.equal(result[0].answer, '$x=1$')
  assert.equal(result[0].status, 'done')
  assert.equal(result[0].model, 'mock')
  assert.equal(result[0].citations.length, 1)
})

test('unanswered and interrupted questions are never relabeled completed', () => {
  const result = messagesToTurns([
    { id: 'u1', role: 'user', content: '失败前的问题' },
    { id: 'u2', role: 'user', content: '另一题' },
    { id: 'a2', role: 'assistant', content: '部分', status: 'stopped' },
  ])
  assert.equal(result[0].status, 'unanswered')
  assert.equal(result[1].status, 'stopped')
  assert.match(result[1].error, /未完整/)
})

test('old no-evidence replies do not present citations as proof', () => {
  const result = messagesToTurns([{ id:'a1', role:'assistant', content:'未找到依据：资料不足', citations:[{index:1}], status:'legacy' }])
  assert.equal(result[0].question, '')
  assert.equal(result[0].status, 'no-evidence')
  assert.deepEqual(result[0].citations, [])
})

test('cursor pages can be prepended before pairing a boundary answer', () => {
  const newest = [{ id:'a1', role:'assistant', content:'答案', status:'legacy' }]
  const earlier = [{ id:'u1', role:'user', content:'问题' }]
  const result = messagesToTurns([...earlier, ...newest])
  assert.equal(result.length, 1)
  assert.equal(result[0].question, '问题')
  assert.equal(result[0].status, 'legacy')
})
