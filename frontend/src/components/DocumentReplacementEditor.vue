<script setup>
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { ElButton, ElProgress } from 'element-plus'
import { replaceDocumentFile, requestApi } from '../api.js'

const props = defineProps({ doc: { type: Object, required: true }, csrfToken: { type: String, required: true } })
const emit = defineEmits(['close', 'saved', 'session-expired'])
const target = ref(null)
const file = ref(null)
const loading = ref(false)
const saving = ref(false)
const uncertain = ref(false)
const percent = ref(0)
const error = ref('')
const lifetime = new AbortController()

async function load() {
  if (saving.value || loading.value) return
  loading.value = true
  error.value = ''
  target.value = null
  file.value = null
  try {
    const data = await requestApi(`/api/docs/${props.doc.id}/replacement`, { signal: lifetime.signal })
    if (!/^[a-f0-9]{64}$/.test(data.version || '')) throw new Error('未能读取资料版本，请重试读取。')
    target.value = data
    uncertain.value = false
  } catch (cause) {
    if (cause.status !== -1) error.value = cause.message
    if (cause.status === 401) emit('session-expired')
  } finally { loading.value = false }
}

function choose(event) {
  file.value = event.target.files?.[0] || null
  error.value = ''
  percent.value = 0
}

async function save() {
  if (saving.value || loading.value || uncertain.value || !target.value || !file.value) return
  const info = target.value
  if (!file.value.name.toLowerCase().endsWith(`.${info.file_type}`)) {
    error.value = `请选择 .${info.file_type} 格式的新文件。`
    return
  }
  if (!file.value.size || file.value.size > info.max_upload_mb * 1024 * 1024) {
    error.value = `新文件不能为空，最多 ${info.max_upload_mb}MB。`
    return
  }
  if (!window.confirm(`用「${file.value.name}」更新「${info.filename}」？\n将备份服务器旧版并更新正文和检索索引，保留资料名称、分类和所属知识库。\n你的本机原文件不变。旧对话的引用片段不会自动更新。`)) return
  saving.value = true
  percent.value = 0
  error.value = ''
  try {
    const result = await replaceDocumentFile(file.value, props.doc.id, info.version, props.csrfToken, {
      signal: lifetime.signal, onProgress: value => { percent.value = value },
    })
    file.value = null
    emit('saved', result)
  } catch (cause) {
    if (cause.status === -1) return
    error.value = cause.message
    if ([0, 408, 409].includes(cause.status)) {
      uncertain.value = true
      error.value += ' 请先重新读取版本信息，核对服务器结果后再操作，不自动重试。'
    }
    if (cause.status === 401) emit('session-expired')
  } finally { saving.value = false }
}

function close() {
  if (saving.value) return
  if (file.value && !window.confirm('已选择新文件但尚未完成替换，确定关闭？服务器已完成的操作不会被撤销。')) return
  emit('close')
}
function guardUnload(event) {
  if (file.value || saving.value) { event.preventDefault(); event.returnValue = '' }
}
onMounted(() => { window.addEventListener('beforeunload', guardUnload); load() })
onBeforeUnmount(() => { lifetime.abort(); window.removeEventListener('beforeunload', guardUnload) })
</script>

<template>
  <form class="replacement-editor" aria-labelledby="replacement-title" :aria-busy="loading || saving" @submit.prevent="save">
    <h4 id="replacement-title">替换新版本 · {{ target?.filename || doc.filename }}</h4>
    <p>新文件校验、解析和向量生成成功后再更新，旧版会自动备份。仅支持相同格式，资料名称和手动分类保留。</p>
    <p v-if="loading" role="status">正在读取当前版本…</p>
    <label v-if="target" for="replacement-file">选择新文件（.{{ target.file_type }}，最多 {{ target.max_upload_mb }}MB）<input id="replacement-file" type="file" :accept="`.${target.file_type}`" :disabled="saving || loading" @change="choose" /></label>
    <div v-if="saving" role="status"><ElProgress :percentage="percent" /><p>{{ percent === 100 ? '传输完成，正在校验、解析并更新索引，请等待服务器确认。' : '正在传输新文件，此进度不代表替换已完成。' }}</p></div>
    <p v-if="error" class="replacement-error" role="alert">{{ error }}</p>
    <div class="replacement-actions"><ElButton type="primary" native-type="submit" :loading="saving" :disabled="loading || !target || !file || uncertain">备份并替换</ElButton><ElButton :disabled="loading || saving" @click="load">重新读取版本信息</ElButton><ElButton :disabled="saving" @click="close">关闭替换</ElButton></div>
  </form>
</template>

<style scoped>
.replacement-editor{padding:18px;background:var(--app-surface, #fff);border:1px solid var(--app-border, #bfcfb2);border-radius:10px;margin:20px 0}.replacement-editor h4{margin:0;overflow-wrap:anywhere}.replacement-editor p{font-size:12px;line-height:1.8;color:var(--app-text, #61745b)}.replacement-editor label{display:flex;flex-direction:column;gap:10px;margin:16px 0;font-size:12px}.replacement-editor input{box-sizing:border-box;max-width:100%;padding:10px;border:1px dashed var(--app-border, #bfcfb2);border-radius:7px}.replacement-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:14px}.replacement-actions .el-button+.el-button{margin-left:0}.replacement-editor .replacement-error{color:var(--app-danger, #a64536);background:var(--app-danger-bg, #fbefea);padding:10px}
</style>
