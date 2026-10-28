const WORDS = /\p{Script=Han}+|[\p{Script=Latin}\p{Script=Greek}\p{N}_^=+.-]{2,}/gu
const STOP_WORDS = new Set(['请', '请问', '帮', '帮我', '解释', '说明', '求', '求解', '解答', '计算', '证明', '为什么', '如何', '怎么', '什么', '这个', '这道', '问题', '一下', '的', '是', '了', '和', '与', '及', '中', '吗', '呢'])
const segmenter = typeof Intl.Segmenter === 'function' ? new Intl.Segmenter('zh-CN', { granularity: 'word' }) : null

function chineseKeywords(text) {
  if (!segmenter) return text.split(/(?:请问|帮我|解释|说明|求解|解答|为什么|如何|怎么|什么|的|是|请)/u)
  const words = []
  let characters = ''
  const flush = () => { if (characters.length >= 2) words.push(characters); characters = '' }
  for (const { segment } of segmenter.segment(text)) {
    if (STOP_WORDS.has(segment)) { flush(); continue }
    // ICU may split a mathematical term such as 判别式 into individual characters.
    if (segment.length === 1) characters += segment
    else { flush(); words.push(segment) }
  }
  flush()
  return words
}

export function citationKeywords(question) {
  const tokens = String(question || '').match(WORDS) || []
  const words = tokens.flatMap(token => /^\p{Script=Han}+$/u.test(token) ? chineseKeywords(token) : [token])
  return [...new Set(words.filter(word => word.length >= 2 && !STOP_WORDS.has(word)))].sort((a, b) => b.length - a.length).slice(0, 8)
}

export function splitHighlightedText(text, keywords) {
  const terms = [...new Set(keywords)].filter(Boolean).sort((a, b) => b.length - a.length)
  if (!terms.length) return [{ text, highlighted: false }]
  const escaped = terms.map(term => term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'))
  const matcher = new RegExp(`(${escaped.join('|')})`, 'giu')
  return text.split(matcher).filter(Boolean).map(part => ({
    text: part,
    highlighted: terms.some(term => part.toLocaleLowerCase() === term.toLocaleLowerCase()),
  }))
}
