<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { ElButton, ElTag } from 'element-plus'
import { requestApi } from '../api.js'
import { streamChat } from '../chat-stream.js'
import { normalizeRelated } from '../chat-related.js'
import ImageQuestion from './ImageQuestion.vue'
import { messagesToTurns } from '../chat-history.js'
import { citationKeywords, splitHighlightedText } from '../citation-highlight.js'

const AnswerContent = defineAsyncComponent(() => import('./AnswerContent.vue'))
const props = defineProps({ kb: { type: Object, required: true }, csrfToken: { type: String, default: '' }, guest: { type: Boolean, default: false } })
const emit = defineEmits(['session-expired'])
const panelId = useId()
const question = ref('')
const liveTurns = ref([])
const savedMessages = ref([])
const turns = computed(() => [...messagesToTurns(savedMessages.value), ...liveTurns.value])
const history = ref([])
const historyBusy = ref(false)
const historyError = ref('')
const historyNotice = ref('')
const historyPage = ref(1)
const historyTotal = ref(0)
const earlierCursor = ref(null)
const conversationId = ref(null)
const busy = ref(false)
const mode = ref(null)
const modeError = ref('')
const error = ref('')
const source = ref(null)
const sourceLoading = ref(false)
const sourceError = ref('')
let alive = true
let sequence = 0
let requestController
let sourceController
let sourceRevision = 0
let historyRevision = 0
let historyController
const lifetime = new AbortController()

function snippetParts(snippet, questionText) {
  return splitHighlightedText(snippet || '', citationKeywords(questionText || ''))
}

function originalFileLabel(filename) {
  if (/\.pdf$/i.test(filename || '')) return '打开 PDF 原文件'
  if (/\.(png|jpe?g)$/i.test(filename || '')) return '打开图片原文件'
  return '下载原始文件'
}

async function checkMode() {
  modeError.value = ''
  try {
    const health = await requestApi('/api/health', { signal: lifetime.signal })
    if (alive) mode.value = health.llm
  } catch (cause) {
    if (alive) modeError.value = cause.message
  }
}

async function send() {
  const text = question.value.trim()
  if (!text || busy.value || historyBusy.value || !mode.value) return
  if (!mode.value.mock && !mode.value.configured) {
    error.value = '尚未配置真实模型，请先完成模型配置。'
    return
  }
  busy.value = true
  error.value = ''
  const id = ++sequence
  liveTurns.value.push({ id: `live-${id}`, question: text, answer: '', citations: [], status: 'streaming', info: null, error: '', model: mode.value.mock ? 'mock' : null })
  const turn = liveTurns.value[liveTurns.value.length - 1]
  question.value = ''
  requestController = new AbortController()
  try {
    await streamChat({ kb_ids: [props.kb.id], question: text, ...(!props.guest && conversationId.value ? { conversation_id: conversationId.value } : {}) }, props.csrfToken, {
      signal: AbortSignal.any([lifetime.signal, requestController.signal]),
      publicOnly: props.guest,
      onEvent(event, data) {
        if (!alive) return
        if (event === 'meta') conversationId.value = data.conversation_id
        if (event === 'delta') turn.answer += data.text
        if (!props.guest && event === 'citation' && !turn.citations.some(cite => cite.index === data.index)) turn.citations.push(data)
        if (event === 'done') {
          if (typeof data.answer === 'string') turn.answer = data.answer
          if (Array.isArray(data.citations)) turn.citations = props.guest ? [] : data.citations
          turn.info = data
          turn.related = normalizeRelated(data)
          turn.model = data.model || turn.model
          turn.status = data.refused || data.declined ? 'no-evidence' : 'done'
          if (turn.status === 'no-evidence') turn.citations = []
        }
      },
    })
  } catch (cause) {
    if (!alive) return
    turn.status = cause.status === -1 ? 'stopped' : 'failed'
    turn.error = cause.message
    if (cause.status === 401) emit('session-expired')
  } finally {
    if (alive) {
      busy.value = false
      await loadHistory()
    }
  }
}

function appendImageText(text) {
  const combined = [question.value, text].filter(Boolean).join('\n')
  if (combined.length > 2000) {
    error.value = '加入后超过 2000 字，请缩短草稿或识别文本。'
    return false
  }
  question.value = combined
  error.value = ''
  return true
}

function stop() { requestController?.abort() }

function closeSource() {
  ++sourceRevision
  sourceController?.abort()
  source.value = null
  sourceError.value = ''
  sourceLoading.value = false
}

function newConversation() {
  if (busy.value) return
  ++historyRevision
  historyController?.abort()
  historyBusy.value = false
  liveTurns.value = []
  savedMessages.value = []
  earlierCursor.value = null
  conversationId.value = null
  error.value = ''
  closeSource()
}

function historyFailure(cause) {
  if (!alive || cause.status === -1) return
  historyError.value = cause.status === 404 ? '历史接口暂不可用或对话已删除，请重启后端并刷新历史。' : cause.message
  if (cause.status === 401) emit('session-expired')
}

async function loadHistory(page = 1) {
  if (props.guest || historyBusy.value || !alive) return
  const version = ++historyRevision
  historyController = new AbortController()
  historyBusy.value = true
  historyError.value = ''
  try {
    const data = await requestApi(`/api/conversations?kb_id=${encodeURIComponent(props.kb.id)}&page=${page}&size=20`, {
      signal: AbortSignal.any([lifetime.signal, historyController.signal]),
    })
    if (!alive || version !== historyRevision) return
    history.value = page === 1 ? data.items : [...history.value, ...data.items.filter(item => !history.value.some(old => old.id === item.id))]
    historyTotal.value = data.total
    historyPage.value = page
  } catch (cause) {
    if (version === historyRevision) historyFailure(cause)
  } finally {
    if (alive && version === historyRevision) historyBusy.value = false
  }
}

async function openConversation(item, earlier = false) {
  if (busy.value || historyBusy.value) return
  const version = ++historyRevision
  historyController = new AbortController()
  historyBusy.value = true
  historyError.value = ''
  historyNotice.value = ''
  try {
    const query = earlier && earlierCursor.value ? `?before_id=${encodeURIComponent(earlierCursor.value)}` : ''
    const data = await requestApi(`/api/conversations/${item.id}/messages${query}`, {
      signal: AbortSignal.any([lifetime.signal, historyController.signal]),
    })
    if (!alive || version !== historyRevision) return
    if (!data.conversation.kb_ids.includes(props.kb.id)) throw new Error('对话不属于当前知识库。')
    if (earlier) savedMessages.value = [...data.items.filter(row => !savedMessages.value.some(old => old.id === row.id)), ...savedMessages.value]
    else {
      savedMessages.value = data.items
      liveTurns.value = []
      question.value = ''
      error.value = ''
      closeSource()
    }
    conversationId.value = data.conversation.id
    earlierCursor.value = data.has_more ? data.next_before_id : null
    historyNotice.value = '历史消息已打开，可以继续追问。'
  } catch (cause) {
    if (version === historyRevision) historyFailure(cause)
  } finally {
    if (alive && version === historyRevision) historyBusy.value = false
  }
}

async function renameConversation(item) {
  if (busy.value || historyBusy.value) return
  const title = window.prompt('新的对话标题（1–120 个字符）：', item.title)
  if (title === null) return
  if (!title.trim() || title.trim().length > 120) {
    historyError.value = '标题需为 1–120 个字符。'
    return
  }
  historyBusy.value = true
  historyError.value = ''
  historyNotice.value = ''
  let changed = false
  try {
    await requestApi(`/api/conversations/${item.id}`, { method: 'PATCH', body: { title: title.trim() }, csrfToken: props.csrfToken, signal: lifetime.signal })
    if (alive) {
      historyNotice.value = '标题已保存。'
      changed = true
    }
  } catch (cause) { historyFailure(cause) }
  finally { if (alive) historyBusy.value = false }
  if (alive && changed) await loadHistory()
}

async function deleteConversation(item) {
  if (busy.value || historyBusy.value) return
  if (!window.confirm(`删除对话「${item.title}」及其消息？不可撤销；知识库和资料会保留。`)) return
  historyBusy.value = true
  historyError.value = ''
  historyNotice.value = ''
  let changed = false
  try {
    await requestApi(`/api/conversations/${item.id}`, { method: 'DELETE', csrfToken: props.csrfToken, signal: lifetime.signal })
    if (!alive) return
    if (conversationId.value === item.id) newConversation()
    historyNotice.value = '所选对话及消息已删除，知识库资料未改变。'
    changed = true
  } catch (cause) { historyFailure(cause) }
  finally { if (alive) historyBusy.value = false }
  if (alive && changed) await loadHistory()
}

async function viewSource(citation) {
  if (props.guest) return
  const version = ++sourceRevision
  sourceController?.abort()
  sourceController = new AbortController()
  source.value = { citation, chunk: null }
  sourceLoading.value = true
  sourceError.value = ''
  try {
    const seq = Number.isInteger(citation.seq) && citation.seq >= 0 ? citation.seq : 0
    const page = Math.floor(seq / 5) + 1
    const data = await requestApi(`/api/docs/${encodeURIComponent(citation.doc_id)}/preview?page=${page}&size=5`, {
      signal: AbortSignal.any([lifetime.signal, sourceController.signal]),
    })
    if (!alive || version !== sourceRevision) return
    const chunk = data.items.find(item => item.id === citation.chunk_id)
    if (!chunk) sourceError.value = '引用片段可能已更新，请重新提问以获取当前资料。'
    else source.value = { citation, chunk }
  } catch (cause) {
    if (!alive || version !== sourceRevision || cause.status === -1) return
    sourceError.value = cause.message
    if (cause.status === 401) emit('session-expired')
  } finally {
    if (alive && version === sourceRevision) sourceLoading.value = false
  }
}

onMounted(() => { checkMode(); loadHistory() })
onBeforeUnmount(() => {
  alive = false
  ++sourceRevision
  ++historyRevision
  historyController?.abort()
  requestController?.abort()
  sourceController?.abort()
  lifetime.abort()
})
</script>

<template>
  <section class="chat-panel" :aria-labelledby="`${panelId}-title`">
    <div class="chat-heading"><div><h3 :id="`${panelId}-title`">基于「{{ kb.name }}」提问</h3><p>{{ guest ? '游客仅基于公共资料单次提问，不保存历史；查看引用和继续追问请登录。' : '使用当前知识库中的资料，支持在同一对话中继续追问。' }}</p></div><ElButton size="small" :disabled="busy || historyBusy || (!turns.length && !conversationId)" @click="newConversation">新对话</ElButton></div>
    <div class="mode-note"><ElTag size="small" :type="mode?.mock ? 'warning' : 'info'">{{ !mode ? '正在检查模型模式' : mode.mock ? '模拟模式 · 模板回答' : '真实模型模式' }}</ElTag><span v-if="mode?.mock">当前只验收检索、流式传输和展示；模板回答可能与题目无关。</span><span v-else-if="mode">{{ mode.configured ? '结合引用原文核对答案。' : '尚未配置模型。' }}</span></div>
    <p v-if="modeError" class="chat-error" role="alert">{{ modeError }} <ElButton size="small" :disabled="busy" @click="checkMode">重新检查模式</ElButton></p>
    <section v-if="!guest" class="history-panel" :aria-labelledby="`${panelId}-history`" :aria-busy="historyBusy"><div class="chat-heading"><h4 :id="`${panelId}-history`">此知识库的对话历史</h4><ElButton size="small" :disabled="busy" :loading="historyBusy" @click="loadHistory()">刷新历史</ElButton></div><p v-if="historyError" class="chat-error" role="alert">{{ historyError }}</p><p v-if="historyNotice" class="chat-hint" role="status">{{ historyNotice }}</p><p v-if="!historyBusy && !historyError && !history.length" class="chat-hint">暂无历史，发送问题后会自动保存。</p><ul class="history-list"><li v-for="item in history" :key="item.id" :class="{ active: conversationId === item.id }"><button class="history-open" type="button" :disabled="busy || historyBusy" :aria-pressed="conversationId === item.id" @click="openConversation(item)">{{ item.title || '未命名对话' }}</button><div><ElButton size="small" :disabled="busy || historyBusy" @click="renameConversation(item)">改名</ElButton><ElButton size="small" type="danger" plain :disabled="busy || historyBusy" @click="deleteConversation(item)">删除</ElButton></div></li></ul><ElButton v-if="history.length < historyTotal" size="small" :disabled="busy || historyBusy" @click="loadHistory(historyPage + 1)">更多历史</ElButton></section>
    <ElButton v-if="earlierCursor && conversationId" size="small" :disabled="busy || historyBusy" @click="openConversation({ id: conversationId }, true)">加载更早消息</ElButton>
    <p v-if="!turns.length" class="chat-empty">输入数学问题开始对话，或从历史记录中继续。</p>
    <div class="chat-turns"><article v-for="turn in turns" :key="turn.id" class="chat-turn"><div v-if="turn.question" class="user-message"><span>你</span><p>{{ turn.question }}</p></div><div class="assistant-message"><div class="answer-heading"><strong>MathRAG</strong><ElTag v-if="turn.status === 'streaming'" size="small">生成中</ElTag><ElTag v-else-if="turn.status === 'no-evidence'" type="warning" size="small">资料依据不足</ElTag><ElTag v-else-if="turn.status === 'stopped' || turn.status === 'failed'" type="warning" size="small">部分回答</ElTag><ElTag v-else-if="turn.status === 'legacy'" type="info" size="small">旧历史记录</ElTag><ElTag v-if="turn.model === 'mock'" type="warning" size="small">模拟模板</ElTag></div><AnswerContent v-if="turn.answer" :text="turn.answer" /><p v-else-if="turn.status === 'streaming'" class="chat-hint" role="status">正在检索资料并等待回答…</p><p v-else-if="turn.status === 'unanswered'" class="chat-hint">这条问题没有已保存的回答，可以继续追问或开始新对话。</p><p v-if="turn.error" class="chat-error" role="alert">{{ turn.error }}</p><p v-if="turn.status === 'no-evidence'" class="chat-hint">请补充相关资料或重新描述问题；这条回答不作为有据解答展示。</p><div v-if="turn.citations.length" class="citations"><h4>检索到的参考片段</h4><details v-for="cite in turn.citations" :key="cite.index"><summary>[{{ cite.index }}] {{ cite.doc_name }}<span v-if="cite.page"> · 第 {{ cite.page }} 页</span></summary><p><template v-for="(part, index) in snippetParts(cite.snippet, turn.question)" :key="index"><mark v-if="part.highlighted">{{ part.text }}</mark><template v-else>{{ part.text }}</template></template></p><ElButton size="small" @click="viewSource(cite)">查看对应正文</ElButton></details></div><section v-if="!guest && turn.status === 'done' && (turn.related?.questions.length || turn.related?.materials.length)" class="related-panel"><h4>继续探索</h4><div class="related-questions"><ElButton v-for="text in turn.related.questions" :key="text" size="small" :disabled="busy || historyBusy" @click="question = text">{{ text }}</ElButton></div><ul v-if="turn.related.materials.length"><li v-for="material in turn.related.materials" :key="material.chunk_id"><ElButton text size="small" @click="viewSource(material)">{{ material.doc_name || '相关资料' }}<span v-if="material.page"> · 第 {{ material.page }} 页</span></ElButton></li></ul></section></div></article></div>
    <ImageQuestion :guest="guest" :disabled="busy || historyBusy" :csrf-token="csrfToken" :append-text="appendImageText" @session-expired="emit('session-expired')" />
    <form class="chat-form" @submit.prevent="send"><label :for="`${panelId}-question`">你的数学问题<textarea :id="`${panelId}-question`" v-model="question" name="question" rows="3" maxlength="2000" required :disabled="busy || historyBusy" placeholder="例如：解方程 x²−3x+2=0，并说明步骤。也可以追问：第二步为什么这样变形？"></textarea></label><div class="chat-form-actions"><span>{{ question.length }}/2000</span><ElButton v-if="busy" type="warning" @click="stop">停止生成</ElButton><ElButton v-else type="primary" native-type="submit" :disabled="!question.trim() || !mode || historyBusy">发送问题</ElButton></div></form><p v-if="error" class="chat-error" role="alert">{{ error }}</p>
    <p v-if="guest" class="chat-hint">游客每分钟最多提问 10 次。此处不提供引用片段和正文入口，回答可能依据公开资料内容；登录后可查看引用。</p>
    <p v-else class="chat-hint">刷新后重新打开知识库，再点击历史标题即可继续追问。“新对话”只清空当前展示；删除历史则会永久删除所选对话及消息，不影响知识库资料。</p>
    <section v-if="source" class="source-preview" :aria-busy="sourceLoading"><div class="chat-heading"><h4>{{ source.citation.doc_name }} · 引用正文</h4><ElButton size="small" @click="closeSource">关闭正文</ElButton></div><p v-if="sourceLoading" role="status">正在定位引用片段…</p><p v-if="sourceError" class="chat-error" role="alert">{{ sourceError }}</p><template v-if="source.chunk"><p class="chat-hint">片段 {{ source.chunk.seq + 1 }}<span v-if="source.chunk.page"> · 原文第 {{ source.chunk.page }} 页</span></p><pre>{{ source.chunk.content }}</pre><p class="chat-hint">原文件采用当前版本；若资料已替换，旧引用不会自动跳转到新版片段。</p><a class="original-file-link" :href="`/api/docs/${encodeURIComponent(source.citation.doc_id)}/file`" target="_blank" rel="noopener noreferrer">{{ originalFileLabel(source.citation.doc_name) }}</a></template></section>
  </section>
</template>

<style scoped>
.chat-panel{margin-top:24px;border:1px solid var(--app-border, #dbe5d2);border-radius:12px;padding:23px;background:var(--app-surface, #fcfdf9)}.chat-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.chat-heading h3{margin:0;font-size:17px}.chat-heading h4{margin:0;font-size:14px;overflow-wrap:anywhere}.chat-heading p,.chat-hint{font-size:12px;line-height:1.9;color:var(--app-muted, #7b8b72);margin:9px 0}.mode-note{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:18px 0}.mode-note>span{font-size:11px;color:var(--app-muted, #8b7b55);line-height:1.8}.chat-empty{font-size:13px;line-height:1.9;color:var(--app-muted, #839175);background:var(--app-soft, #f1f5e9);border-radius:9px;padding:20px}.chat-turn{margin:24px 0}.user-message{background:var(--app-soft, #eaf1e2);padding:16px 20px;border-radius:12px;margin-left:35px}.user-message>span{font-size:11px;color:var(--app-muted, #6c885b)}.user-message p{font-size:14px;white-space:pre-wrap;overflow-wrap:anywhere;line-height:1.9;margin:7px 0 0}.assistant-message{border:1px solid var(--app-border, #e1e8d9);background:var(--app-surface, #fff);border-radius:12px;margin-top:13px;padding:18px 20px}.answer-heading{display:flex;gap:12px;align-items:center;font-size:13px}.citations{border-top:1px solid var(--app-border, #e6ecdf);margin-top:18px;padding-top:12px}.citations h4{font-size:12px;color:var(--app-muted, #6e8061)}.citations details{font-size:12px;border:1px solid var(--app-border, #e6ecdf);padding:12px;border-radius:8px;margin:9px 0}.citations summary{cursor:pointer;line-height:1.8;overflow-wrap:anywhere}.citations p{white-space:pre-wrap;line-height:1.9;overflow-wrap:anywhere}.chat-form{margin-top:23px}.chat-form label{display:flex;flex-direction:column;gap:10px;font-size:12px;color:var(--app-text, #586e4e)}.chat-form textarea{resize:vertical;min-height:90px;border:1px solid var(--app-border, #ccd9bf);border-radius:9px;font:13px/1.9 var(--app-font, "Segoe UI","Microsoft YaHei",sans-serif);padding:13px;color:var(--app-text, #304830);background:var(--app-surface, #fff)}.chat-form textarea:focus{outline:2px solid var(--app-border, #94b59a);outline-offset:2px}.chat-form-actions{display:flex;justify-content:space-between;align-items:center;margin-top:12px}.chat-form-actions span{font-size:11px;color:var(--app-muted, #8a967f)}.chat-error{font-size:12px;line-height:1.9;color:var(--app-danger, #a64536);background:var(--app-danger-bg, #fbefea);padding:12px;border-radius:8px}.source-preview{background:var(--app-soft, #f2f6ec);border:1px solid var(--app-border, #dce6d1);border-radius:10px;padding:18px;margin-top:18px}.source-preview pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.9 var(--app-font, "Segoe UI","Microsoft YaHei",sans-serif)}@media(max-width:550px){.chat-panel{padding:15px}.user-message{margin-left:12px}.assistant-message{padding:14px}.chat-heading{align-items:flex-start}.chat-heading .el-button{flex-shrink:0}}
.history-panel{border:1px solid var(--app-border, #e1e8d8);background:var(--app-soft, #f5f8ee);padding:15px;border-radius:10px;margin:18px 0}.history-list{list-style:none;margin:10px 0;padding:0}.history-list li{display:flex;align-items:center;gap:10px;padding:9px;border:1px solid transparent;border-radius:8px}.history-list li.active{background:var(--app-soft, #e5efdc);border-color:var(--app-border, #c5d7b5)}.history-open{flex:1;min-width:0;text-align:left;font:12px/1.8 var(--app-font, "Segoe UI","Microsoft YaHei",sans-serif);overflow-wrap:anywhere;border:0;background:transparent;color:var(--app-text, #3d6042);cursor:pointer;padding:5px}.history-open:focus-visible{outline:2px solid var(--app-accent, #8bab7a);border-radius:5px}.history-open:disabled{cursor:wait;opacity:.65}.history-list li>div{display:flex;gap:6px;flex-shrink:0}.history-list .el-button+.el-button{margin-left:0}.answer-heading{flex-wrap:wrap}@media(max-width:550px){.history-list li{flex-wrap:wrap}.history-open{flex-basis:100%}.history-list li>div{margin-left:auto}}
.citations mark{background:#ffe18a;color:#3d3b22;border-radius:2px;padding:0 1px}.original-file-link{display:inline-block;margin-top:8px;color:var(--app-text, #2b775b);font-size:12px;font-weight:600;text-decoration:underline}
.related-panel{border-top:1px solid var(--app-border, #dce5d3);margin-top:16px;padding-top:8px}.related-panel h4{font-size:13px}.related-questions{display:flex;gap:8px;flex-wrap:wrap}.related-questions .el-button{height:auto;white-space:normal;line-height:1.8;margin:0;text-align:left}.related-panel ul{list-style:none;padding:0}.related-panel li .el-button{white-space:normal;height:auto;text-align:left}
</style>
