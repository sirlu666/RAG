<script setup>
import { computed, defineAsyncComponent, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElButton } from 'element-plus'
import { requestApi, recognizeDocumentFormula } from '../api.js'
import { fileProblem } from '../document-upload.js'
const AnswerContent = defineAsyncComponent(() => import('./AnswerContent.vue'))

const props = defineProps({ doc: { type: Object, required: true }, csrfToken: { type: String, required: true } })
const isImage = computed(() => ['png', 'jpg', 'jpeg'].includes(props.doc.file_type))
const emit = defineEmits(['close', 'saved', 'session-expired'])
const text = ref('')
const original = ref('')
const version = ref('')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const uncertain = ref(false)
const previewText = ref('')
const recognizing = ref(false)
const formulaInput = ref(null)
const formulaLatex = ref('')
const busy = computed(() => loading.value || saving.value || recognizing.value)
const dirty = computed(() => text.value !== original.value)
const lifetime = new AbortController()

async function load() {
  if (busy.value) return
  if (dirty.value && !window.confirm('重新读取将丢弃本页未保存修改。请先复制需要保留的内容，确定重新读取？')) return
  loading.value = true
  error.value = ''
  try {
    const data = await requestApi(`/api/docs/${props.doc.id}/text`, { signal: lifetime.signal })
    text.value = data.content
    original.value = data.content
    version.value = data.version
    formulaLatex.value = ''
    previewText.value = ''
    uncertain.value = false
  } catch (cause) {
    if (cause.status !== -1) error.value = cause.message
    if (cause.status === 401) emit('session-expired')
  } finally {
    loading.value = false
  }
}

async function save() {
  if (busy.value || !dirty.value || !version.value || uncertain.value) return
  if (!window.confirm(`保存「${props.doc.filename}」的新正文并更新检索索引？\n服务器将保留旧版备份。${isImage.value ? '服务器原图保持不变；' : ''}电脑上的原文件不变；旧对话中的引用片段不会自动更新。`)) return
  saving.value = true
  error.value = ''
  try {
    await requestApi(`/api/docs/${props.doc.id}/text`, {
      method: 'PUT', body: { content: text.value, version: version.value },
      csrfToken: props.csrfToken, signal: lifetime.signal, timeoutMs: 120000,
    })
    original.value = text.value
    emit('saved')
  } catch (cause) {
    if (cause.status === -1) return
    error.value = cause.message
    if (cause.status === 0 || cause.status === 409) {
      uncertain.value = true
      error.value += ' 请先复制本页修改，再重新读取服务器正文核对版本，避免重复保存。'
    }
    if (cause.status === 401) emit('session-expired')
  } finally {
    saving.value = false
  }
}

function close() {
  if (busy.value) return
  if (dirty.value && !window.confirm('有未保存修改，确定放弃并关闭？')) return
  emit('close')
}

function guardUnload(event) {
  if (dirty.value || busy.value) { event.preventDefault(); event.returnValue = '' }
}

async function recognizeFormula(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || busy.value || !version.value || uncertain.value) return
  error.value = ''
  if (!/\.(png|jpe?g)$/i.test(file.name) || fileProblem(file)) {
    error.value = '请选择不超过 50MB 的 PNG/JPG/JPEG 单条公式截图。'
    return
  }
  recognizing.value = true
  formulaLatex.value = ''
  try {
    const result = await recognizeDocumentFormula(file, props.doc.id, version.value, props.csrfToken, { signal: lifetime.signal })
    formulaLatex.value = result.latex
  } catch (cause) {
    if (cause.status !== -1) error.value = cause.message
    if (cause.status === 401) emit('session-expired')
    if (cause.status === 409) uncertain.value = true
  } finally {
    recognizing.value = false
  }
}

function appendFormula() {
  if (busy.value || !formulaLatex.value.trim() || uncertain.value) return
  const addition = `\n\n$$\n${formulaLatex.value.trim()}\n$$`
  if (text.value.length + addition.length > 200000) {
    error.value = '追加公式后将超过 20 万字符，请先缩短正文。'
    return
  }
  text.value += addition
  formulaLatex.value = ''
}
onMounted(() => { window.addEventListener('beforeunload', guardUnload); load() })
onBeforeUnmount(() => { lifetime.abort(); window.removeEventListener('beforeunload', guardUnload) })
</script>

<template>
  <section class="text-editor" aria-labelledby="text-editor-title" :aria-busy="busy">
    <h4 id="text-editor-title">{{ isImage ? '校对识别文字' : '编辑正文' }} · {{ doc.filename }}</h4>
    <p v-if="isImage">校对当前入库文字，最多 20 万字符。首次由正文片段合并，长图可能包含重复文字，请对照原图检查。保存后更新检索内容并保留旧版备份，服务器原图保持不变。</p>
    <p v-else>编辑服务器保存的原始 TXT／Markdown，最多 20 万字符。保存会自动备份旧版并重新切片、生成向量；电脑上的原文件保留。</p>
    <p v-if="isImage"><a :href="`/api/docs/${doc.id}/file`" target="_blank" rel="noopener">打开原图对照</a></p>
    <p v-if="loading" role="status">正在读取正文…</p>
    <label v-if="version" for="document-text">{{ isImage ? '识别文字（可修正错字、数字及 LaTeX 公式）' : '原始正文（Markdown 标记和 LaTeX 可直接编辑）' }}</label>
    <textarea v-if="version" id="document-text" v-model="text" :disabled="busy" maxlength="200000" rows="14" spellcheck="false"></textarea>
    <small v-if="version">{{ text.length }} / 200000 字符 · {{ dirty ? '有未保存修改' : '尚无修改' }}</small>
    <template v-if="isImage && version">
      <p>识别单条印刷公式：截取清晰公式，尽量不含中文说明。识别结果先作为建议显示，核对后追加到正文，再点击保存才会入库。</p>
      <input ref="formulaInput" type="file" accept=".png,.jpg,.jpeg" hidden :disabled="busy || uncertain" aria-label="选择单条公式截图" @change="recognizeFormula" />
      <ElButton :loading="recognizing" :disabled="busy || uncertain" @click="formulaInput?.click()">识别公式截图</ElButton>
      <template v-if="formulaLatex">
        <label for="formula-suggestion">LaTeX 建议（可修改）</label>
        <textarea id="formula-suggestion" v-model="formulaLatex" :disabled="busy" maxlength="10000" rows="3" spellcheck="false"></textarea>
        <ElButton :disabled="busy || uncertain" @click="previewText = `$$\n${formulaLatex}\n$$`">预览公式建议</ElButton>
        <ElButton :disabled="busy || uncertain" @click="appendFormula">追加到待保存正文</ElButton>
      </template>
      <p>独立公式使用 $$ 包围，例如 $$x^2-3x+2=0$$。识别结果可能有误，请对照原图校对。</p>
      <ElButton :disabled="busy" @click="previewText = text">预览文字与公式</ElButton>
      <section v-if="previewText" aria-label="校对内容预览">
        <p>此处预览点击时的文字；修改后请再次点击预览。保存后才会更新检索内容。</p>
        <AnswerContent :text="previewText" />
      </section>
    </template>
    <p v-if="error" class="editor-error" role="alert">{{ error }}</p>
    <p v-if="saving" role="status">正在校验、备份并更新索引，请等待；暂勿关闭页面。</p>
    <p v-if="recognizing" role="status">正在本机识别公式，首次运行可能稍慢；原图和正文均未修改。</p>
    <div class="editor-actions">
      <ElButton type="primary" :loading="saving" :disabled="busy || !version || !dirty || uncertain" @click="save">备份并保存</ElButton>
      <ElButton :disabled="busy" @click="load">重新读取</ElButton>
      <ElButton :disabled="busy" @click="close">关闭编辑</ElButton>
    </div>
  </section>
</template>

<style scoped>
.text-editor{margin:20px 0;padding:18px;border:1px solid var(--app-border, #bfcfb2);border-radius:10px;background:var(--app-surface, #fff)}.text-editor h4{margin:0;overflow-wrap:anywhere}.text-editor p,.text-editor label,.text-editor small{font-size:12px;line-height:1.8;color:var(--app-text, #61745b)}.text-editor textarea{box-sizing:border-box;width:100%;max-width:100%;margin:8px 0;resize:vertical;border:1px solid var(--app-border, #bfcfb2);border-radius:8px;padding:12px;font:14px/1.8 Consolas,'Microsoft YaHei',monospace}.text-editor textarea:focus{outline:2px solid var(--app-accent, #367449)}.editor-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.editor-actions .el-button+.el-button{margin-left:0}.text-editor .editor-error{color:var(--app-danger, #a64536);background:var(--app-danger-bg, #fbefea);padding:10px;border-radius:6px}
</style>
