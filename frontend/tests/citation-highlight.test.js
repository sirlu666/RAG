import test from 'node:test'
import assert from 'node:assert/strict'
import { citationKeywords, splitHighlightedText } from '../src/citation-highlight.js'

test('Chinese questions highlight mathematical terms without requiring the request prefix', () => {
  const question = '请解释一元二次方程的判别式'
  const snippet = '一元二次方程的判别式为 b²−4ac。'
  const keywords = citationKeywords(question)
  const parts = splitHighlightedText(snippet, keywords)
  assert.ok(!keywords.includes(question))
  assert.ok(!keywords.includes('请') && !keywords.includes('解释'))
  assert.ok(parts.some(part => part.highlighted && part.text.includes('方程')))
  assert.ok(parts.some(part => part.highlighted && part.text === '判别式'))
  assert.equal(parts.map(part => part.text).join(''), snippet)
})

test('single-character ICU segments can form a term and keywords remain bounded', () => {
  const keys = citationKeywords('请说明判别式的含义，如何求解方程')
  assert.ok(keys.includes('判别式'))
  assert.ok(!keys.includes('如何') && !keys.includes('求解'))
  assert.ok(citationKeywords('矩阵 函数 导数 极限 数列 向量 概率 积分 不等式 微积分 线性代数').length <= 8)
  assert.deepEqual(citationKeywords('请解释一下'), [])
})

test('formula matching is literal and highlighting preserves untrusted text as text', () => {
  const text = '<img src=x onerror=alert(1)> A+B x^2-3x+2=0 aab'
  const parts = splitHighlightedText(text, ['a+b', 'x^2-3x+2=0'])
  assert.deepEqual(parts.filter(part => part.highlighted).map(part => part.text), ['A+B', 'x^2-3x+2=0'])
  assert.equal(parts.map(part => part.text).join(''), text)
  assert.deepEqual(splitHighlightedText('普通文本', []), [{ text: '普通文本', highlighted: false }])
})
