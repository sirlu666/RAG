import test from 'node:test'
import assert from 'node:assert/strict'
import { renderAnswerMarkdown } from '../src/answer-markdown.js'

test('MathJax renders inline, display and slash-delimited LaTeX locally', () => {
  for (const source of ['$x^2+1$', '$$\n\\frac{1}{2}\n$$', '\\(x+1\\)', '\\[x^2\\]']) {
    assert.match(renderAnswerMarkdown(source), /<svg/)
  }
})

test('Markdown lists and emphasis work while source HTML is escaped', () => {
  const html = renderAnswerMarkdown('**步骤**\n\n1. 配方\n2. 求根\n\n<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>')
  assert.match(html, /<strong>步骤<\/strong>/)
  assert.match(html, /<ol>/)
  assert.doesNotMatch(html, /<script|<img/i)
})

test('dangerous Markdown links are not activated', () => {
  assert.doesNotMatch(renderAnswerMarkdown('[点击](javascript:alert(1))'), /href="javascript:/i)
})

test('code fences do not typeset math; partial formulas remain readable', () => {
  assert.doesNotMatch(renderAnswerMarkdown('```text\n$x^2$\n```'), /<svg/)
  assert.match(renderAnswerMarkdown('推导 $\\frac{1}{'), /推导/)
})
