import test from 'node:test'
import assert from 'node:assert/strict'
import { filterDocuments, hasAutoTags } from '../src/document-filter.js'

const docs = [
  { id: 1, filename: '微积分.TXT', category: '微积分' },
  { id: 2, filename: '线性代数.md', category: '代数' },
  { id: 3, filename: '方程.txt' },
]
test('combines name search and exact category without mutating documents', () => {
  assert.deepEqual(filterDocuments(docs, '  .txt  ').map(doc => doc.id), [1, 3])
  assert.deepEqual(filterDocuments(docs, '积分', '微积分').map(doc => doc.id), [1])
  assert.deepEqual(filterDocuments(docs, '积分', '代数'), [])
  assert.equal(docs.length, 3)
})
test('all categories and uncategorized are distinct, literal user input is safe', () => {
  assert.equal(filterDocuments(docs).length, 3)
  assert.deepEqual(filterDocuments(docs, '', '').map(doc => doc.id), [3])
  assert.deepEqual(filterDocuments(docs, '.*'), [])
  assert.deepEqual(filterDocuments([], '', '微积分'), [])
})

const tagged = [
  { id: 1, filename: '方程讲义.txt', category: '代数', knowledge_points: ['判别式', '一元二次方程'], question_types: ['计算题'], difficulty: '基础' },
  { id: 2, filename: '方程证明.md', category: '代数', knowledge_points: ['判别式'], question_types: ['证明题'], difficulty: '进阶' },
  { id: 3, filename: '未标注.txt', category: '代数' },
]

test('combines automatic labels with name and manual category using exact matches', () => {
  const before = JSON.stringify(tagged)
  assert.deepEqual(filterDocuments(tagged, '方程', '代数', {
    knowledgePoint: '判别式', questionType: '计算题', difficulty: '基础', tagStatus: 'tagged',
  }).map(doc => doc.id), [1])
  assert.deepEqual(filterDocuments(tagged, '', null, { knowledgePoint: '判' }), [])
  assert.deepEqual(filterDocuments(tagged, '', null, { questionType: '证明题', difficulty: '基础' }), [])
  assert.equal(JSON.stringify(tagged), before)
})

test('unlabeled documents remain discoverable and empty results do not change the source', () => {
  assert.deepEqual(filterDocuments(tagged, '', null, { tagStatus: 'untagged' }).map(doc => doc.id), [3])
  assert.deepEqual(filterDocuments(tagged, '', null, { tagStatus: 'tagged' }).map(doc => doc.id), [1, 2])
  assert.deepEqual(filterDocuments(tagged, '', null, { tagStatus: 'untagged', knowledgePoint: '判别式' }), [])
  assert.equal(filterDocuments(tagged).length, 3)
  assert.equal(hasAutoTags({ knowledge_points: [], question_types: [], difficulty: null }), false)
  assert.equal(hasAutoTags({ difficulty: '基础' }), true)
})
