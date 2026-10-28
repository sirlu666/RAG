import MarkdownIt from 'markdown-it'
import { mathjax } from 'mathjax-full/js/mathjax.js'
import { TeX } from 'mathjax-full/js/input/tex.js'
import { SVG } from 'mathjax-full/js/output/svg.js'
import { liteAdaptor } from 'mathjax-full/js/adaptors/liteAdaptor.js'
import { RegisterHTMLHandler } from 'mathjax-full/js/handlers/html.js'
import 'mathjax-full/js/input/tex/ams/AmsConfiguration.js'

const adaptor = liteAdaptor()
RegisterHTMLHandler(adaptor)
const mathDocument = mathjax.document('', {
  InputJax: new TeX({ packages: ['base', 'ams'], maxBuffer: 10000, maxMacros: 1000 }),
  OutputJax: new SVG({ fontCache: 'none' }),
})
const markdown = new MarkdownIt({ html: false, breaks: true, linkify: false })

function mathRule(state, silent) {
  const source = state.src
  const start = state.pos
  const opening = source.startsWith('$$', start) ? '$$' : source.startsWith('\\[', start) ? '\\[' : source.startsWith('\\(', start) ? '\\(' : source[start] === '$' ? '$' : null
  if (!opening) return false
  const closing = opening === '\\[' ? '\\]' : opening === '\\(' ? '\\)' : opening
  let end = source.indexOf(closing, start + opening.length)
  while (end >= 0 && source[end - 1] === '\\' && closing.startsWith('$')) end = source.indexOf(closing, end + closing.length)
  if (end < 0 || end === start + opening.length) return false
  if (!silent) {
    const token = state.push('math', '', 0)
    token.content = source.slice(start + opening.length, end)
    token.meta = { display: opening === '$$' || opening === '\\[' }
  }
  state.pos = end + closing.length
  return true
}

markdown.inline.ruler.before('escape', 'math', mathRule)
markdown.renderer.rules.math = (tokens, index) => {
  const token = tokens[index]
  try {
    if (token.content.length > 10000) return markdown.utils.escapeHtml(token.content)
    const node = mathDocument.convert(token.content, { display: token.meta.display })
    return adaptor.outerHTML(node)
  } catch {
    return `<code>${markdown.utils.escapeHtml(token.content)}</code>`
  }
}

// html:false escapes source HTML; browser DOMPurify is a second check before v-html.
export function renderAnswerMarkdown(text) {
  return markdown.render(text || '')
}
