<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElButton } from 'element-plus'
import { requestApi } from '../api.js'

const props = defineProps({ doc: { type: Object, required: true }, csrfToken: { type: String, required: true }, categories: { type: Array, default: () => [] } })
const emit = defineEmits(['close', 'saved', 'session-expired'])
const filename = ref(props.doc.filename)
const category = ref(props.doc.category || '')
const originalName = ref(props.doc.filename)
const originalCategory = ref(props.doc.category || '')
const version = ref('')
const loading = ref(true)
const saving = ref(false)
const conflict = ref(false)
const error = ref('')
const dirty = computed(() => filename.value !== originalName.value || category.value !== originalCategory.value)
const lifetime = new AbortController()

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await requestApi(`/api/docs/${props.doc.id}/metadata`, { signal: lifetime.signal })
    if (!/^[a-f0-9]{64}$/.test(data.metadata_version || '')) throw new Error('未能读取资料版本，请刷新页面后重新打开编辑。')
    filename.value = originalName.value = data.filename
    category.value = originalCategory.value = data.category || ''
    version.value = data.metadata_version
  } catch (cause) {
    if (cause.status !== -1) error.value = cause.message
    if (cause.status === 401) emit('session-expired')
  } finally { loading.value = false }
}

async function save() {
  if (loading.value || !version.value || saving.value || conflict.value || !dirty.value) return
  saving.value = true
  error.value = ''
  try {
    const result = await requestApi(`/api/docs/${props.doc.id}/metadata`, {
      method: 'PATCH', csrfToken: props.csrfToken, signal: lifetime.signal,
      body: { filename: filename.value, category: category.value, version: version.value },
    })
    originalName.value = filename.value
    originalCategory.value = category.value
    emit('saved', result)
  } catch (cause) {
    if (cause.status === -1) return
    error.value = cause.message
    if (cause.status === 0 || cause.status === 409) {
      conflict.value = true
      error.value += ' 请记下本页输入，关闭编辑并刷新列表核对后再试。'
    }
    if (cause.status === 401) emit('session-expired')
  } finally { saving.value = false }
}

function close() {
  if (saving.value) return
  if (dirty.value && !window.confirm('名称或分类有未保存修改，确定放弃并关闭？')) return
  emit('close')
}
function guardUnload(event) {
  if (dirty.value || saving.value) { event.preventDefault(); event.returnValue = '' }
}
onMounted(() => { window.addEventListener('beforeunload', guardUnload); load() })
onBeforeUnmount(() => { lifetime.abort(); window.removeEventListener('beforeunload', guardUnload) })
</script>

<template>
  <form class="metadata-editor" aria-labelledby="metadata-title" @submit.prevent="save">
    <h4 id="metadata-title">名称与分类 · {{ doc.filename }}</h4>
    <p>保留 .{{ doc.file_type }} 扩展名。分类可以输入新名称，留空表示未分类；自动知识标签另行保留。</p>
    <p v-if="loading" role="status">正在读取最新名称、分类和版本…</p>
    <label for="doc-name">资料名称<input id="doc-name" v-model="filename" required maxlength="255" :disabled="loading || !version || saving" /></label>
    <label for="doc-category">手动分类<input id="doc-category" v-model="category" list="doc-category-options" maxlength="64" :disabled="loading || !version || saving" placeholder="例如：微积分、线性代数" /></label>
    <datalist id="doc-category-options"><option v-for="name in categories.filter(Boolean)" :key="name" :value="name" /></datalist>
    <p v-if="error" class="metadata-error" role="alert">{{ error }}</p>
    <div class="metadata-actions"><ElButton type="primary" native-type="submit" :loading="saving" :disabled="loading || !version || !dirty || conflict">保存名称与分类</ElButton><ElButton v-if="!version && !loading" @click="load">重试读取</ElButton><ElButton :disabled="saving" @click="close">取消编辑</ElButton></div>
  </form>
</template>

<style scoped>
.metadata-editor{background:var(--app-surface, #fff);border:1px solid var(--app-border, #bfcfb2);border-radius:10px;padding:18px;margin:20px 0}.metadata-editor h4{margin:0;overflow-wrap:anywhere}.metadata-editor p{font-size:12px;line-height:1.8;color:var(--app-text, #61745b)}.metadata-editor label{display:flex;flex-direction:column;gap:8px;font-size:12px;margin:14px 0}.metadata-editor input{box-sizing:border-box;width:100%;padding:10px;border:1px solid var(--app-border, #bfcfb2);border-radius:7px;font:inherit}.metadata-editor input:focus{outline:2px solid var(--app-accent, #367449)}.metadata-actions{display:flex;gap:8px;flex-wrap:wrap}.metadata-actions .el-button+.el-button{margin-left:0}.metadata-editor .metadata-error{color:var(--app-danger, #a64536);background:var(--app-danger-bg, #fbefea);padding:10px}
</style>
