<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { ElButton, ElDrawer } from 'element-plus'
import { requestApi } from '../api.js'
import DocumentPanel from './DocumentPanel.vue'
import ChatPanel from './ChatPanel.vue'

const props = defineProps({ csrfToken: { type: String, required: true } })
const emit = defineEmits(['session-expired', 'publication-changed'])
const items = ref([])
const loading = ref(false)
const busy = ref(false)
const loaded = ref(false)
const name = ref('')
const editingId = ref(null)
const error = ref('')
const notice = ref('')
const selectedId = ref(null)
const documentBusy = ref(false)
const documentsOpen = ref(false)
watch(selectedId, () => { documentsOpen.value = false })
const selectedKb = computed(() => items.value.find(item => item.id === selectedId.value))

function report(cause) {
  error.value = cause.message
  if (cause.status === 401) emit('session-expired')
}

async function load() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    items.value = await requestApi('/api/kbs')
    loaded.value = true
  } catch (cause) {
    report(cause)
    loaded.value = false
  } finally {
    loading.value = false
  }
}

function cancelEdit() {
  editingId.value = null
  name.value = ''
}

function edit(item) {
  editingId.value = item.id
  name.value = item.name
  error.value = ''
  notice.value = ''
}

async function save() {
  const trimmed = name.value.trim()
  if (busy.value || loading.value || documentBusy.value) return
  if (!trimmed) {
    error.value = '请输入知识库名称。'
    return
  }
  busy.value = true
  error.value = ''
  notice.value = ''
  const wasEditing = editingId.value !== null
  try {
    await requestApi(wasEditing ? `/api/kbs/${editingId.value}` : '/api/kbs', {
      method: wasEditing ? 'PATCH' : 'POST',
      body: { name: trimmed },
      csrfToken: props.csrfToken,
    })
    cancelEdit()
    notice.value = wasEditing ? '知识库名称已保存。' : '知识库已创建。'
    await load()
  } catch (cause) {
    report(cause)
  } finally {
    busy.value = false
  }
}

async function remove(item) {
  if (busy.value || loading.value || documentBusy.value) return
  if (!window.confirm(`确定删除空知识库「${item.name}」？删除后无法直接撤销。`)) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await requestApi(`/api/kbs/${item.id}`, { method: 'DELETE', csrfToken: props.csrfToken })
    if (editingId.value === item.id) cancelEdit()
    notice.value = '空知识库已删除。'
    await load()
  } catch (cause) {
    report(cause)
  } finally {
    busy.value = false
  }
}

async function togglePublication(item) {
  if (busy.value || loading.value || documentBusy.value) return
  const message = item.is_public
    ? `撤销「${item.name}」的公开访问？新的游客问答和其他账号的正文访问将被禁止，已经显示的回答无法收回。`
    : `公开「${item.name}」？库内所有当前和今后上传的资料将用于游客回答，其他登录账号可以查看引用正文。请确认此库仅含可公开资料。`
  if (!window.confirm(message)) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await requestApi(`/api/kbs/${item.id}/visibility`, { method: 'PUT', csrfToken: props.csrfToken, body: { public: !item.is_public } })
    notice.value = item.is_public ? '已撤销公开。' : '已公开，请在下方公共知识库区域查看。'
    await load()
    emit('publication-changed')
  } catch (cause) { report(cause) }
  finally { busy.value = false }
}

onMounted(load)
</script>

<template>
  <section class="kb-section" aria-labelledby="kb-title" :aria-busy="busy || loading">
    <div class="kb-layout">
    <div class="kb-library">
    <div class="kb-heading"><div><h3 id="kb-title">我的知识库</h3><p>为不同课程分别整理资料，例如高等数学、线性代数。</p></div><ElButton :loading="loading" :disabled="busy" size="small" @click="load">刷新列表</ElButton></div>
    <form class="kb-form" @submit.prevent="save"><label for="kb-name">{{ editingId ? '修改知识库名称' : '新建知识库' }}<input id="kb-name" v-model="name" name="kb-name" maxlength="64" required :disabled="busy || loading || documentBusy" placeholder="输入名称，最多 64 个字符" /></label><ElButton type="primary" native-type="submit" :loading="busy" :disabled="loading || documentBusy">{{ editingId ? '保存修改' : '创建知识库' }}</ElButton><ElButton v-if="editingId" :disabled="busy || documentBusy" @click="cancelEdit">取消修改</ElButton></form>
    <p v-if="notice" class="kb-notice" role="status">{{ notice }}</p>
    <p v-if="error" class="kb-error" role="alert">{{ error }}</p>
    <p v-if="loading" class="kb-hint" role="status">正在读取知识库…</p>
    <p v-else-if="loaded && !items.length" class="kb-empty">还没有知识库，先创建一个吧。</p>
    <ul v-else-if="loaded" class="kb-list"><li v-for="item in items" :key="item.id"><div class="kb-details"><strong>{{ item.name }}</strong><span>{{ item.document_count }} 份文档 · {{ item.is_public ? '已公开' : '私有' }}</span></div><div class="kb-actions"><ElButton size="small" :disabled="busy || loading || documentBusy" @click="togglePublication(item)">{{ item.is_public ? '撤销公开' : '公开此库' }}</ElButton><ElButton size="small" :type="selectedId === item.id ? 'primary' : 'default'" :disabled="busy || loading || documentBusy" :aria-label="`资料：${item.name}`" @click="selectedId = item.id">进入知识库</ElButton><ElButton size="small" :disabled="busy || loading || documentBusy" :aria-label="`改名：${item.name}`" @click="edit(item)">改名</ElButton><ElButton size="small" type="danger" plain :disabled="busy || loading || documentBusy || item.document_count > 0" :title="item.document_count ? '含有文档，须先处理文档' : '删除空知识库'" :aria-label="`删除：${item.name}`" @click="remove(item)">删除</ElButton></div></li></ul>
    <p class="kb-hint">只显示当前账号的知识库。同一账号内名称不能重复；含有文档的知识库暂不允许删除，以保护原文和检索数据。</p>
    </div>
    <div class="kb-conversation">
    <div v-if="selectedKb" class="selected-kb-bar"><div><strong>{{ selectedKb.name }}</strong><span>{{ selectedKb.document_count }} 份资料</span></div><ElButton :aria-expanded="documentsOpen" @click="documentsOpen = true">管理资料</ElButton></div>
    <ElDrawer v-model="documentsOpen" :title="`${selectedKb?.name || ''} · 资料管理`" size="min(880px, 85vw)" append-to-body :destroy-on-close="false" :close-on-click-modal="false">
      <DocumentPanel v-if="selectedKb" :key="selectedKb.id" :kb="selectedKb" :csrf-token="csrfToken" @documents-changed="load" @uploading-change="documentBusy = $event" @session-expired="emit('session-expired')" />
    </ElDrawer>
    <ChatPanel v-if="selectedKb" :key="`chat-${selectedKb.id}`" :kb="selectedKb" :csrf-token="csrfToken" @session-expired="emit('session-expired')" />
    <p v-else class="conversation-empty">选择一个知识库开始对话，或先创建自己的知识库。</p>
    </div>
    </div>
  </section>
</template>

<style scoped>
.kb-library,.kb-conversation{min-width:0}.conversation-empty{display:grid;place-items:center;min-height:250px;padding:24px;text-align:center;color:var(--app-muted,#7d8c74);font-size:14px;background:var(--app-soft,#f5f7ef);border:1px dashed var(--app-border,#dce3d6);border-radius:12px}
.selected-kb-bar{display:flex;align-items:center;justify-content:space-between;gap:16px;border-top:0;padding-top:0;margin-top:0}.selected-kb-bar>div{display:flex;align-items:center;gap:12px}.selected-kb-bar strong{font-size:15px}.selected-kb-bar span{font-size:12px;color:var(--app-muted,#7d8c74)}.kb-list{max-height:240px;overflow-y:auto;scrollbar-gutter:stable}

.kb-section{border:0;margin:0;padding:0}.kb-heading{display:flex;justify-content:space-between;align-items:center;gap:15px}.kb-heading h3{font-size:17px;margin:0;color:var(--app-text, #314c39)}.kb-heading p,.kb-hint{font-size:12px;color:var(--app-muted, #7d8c74);line-height:1.9}.kb-heading p{margin:8px 0 0}.kb-form{display:flex;gap:10px;align-items:end;flex-wrap:wrap;margin-top:20px}.kb-form label{flex:1;min-width:200px;display:flex;flex-direction:column;gap:8px;font-size:12px;color:var(--app-text, #566b54)}.kb-form input{height:39px;width:100%;padding:0 12px;font:inherit;border:1px solid var(--app-border, #dce3d6);border-radius:8px;color:var(--app-text, #263f31);background:var(--app-surface, #fdfefb)}.kb-form input:focus{outline:2px solid var(--app-border, #93bda5);outline-offset:2px}.kb-form .el-button{height:39px;margin-left:0}.kb-list{list-style:none;padding:0;margin:20px 0}.kb-list li{display:flex;justify-content:space-between;gap:15px;align-items:center;border:1px solid var(--app-border, #e5eadf);border-radius:9px;padding:15px;margin-bottom:10px;background:var(--app-surface, #fcfdf9)}.kb-details{min-width:0;display:flex;flex-direction:column;gap:7px}.kb-details strong{font-size:14px;font-weight:550;overflow-wrap:anywhere}.kb-details span{font-size:11px;color:var(--app-muted, #819076)}.kb-actions{flex-shrink:0;display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.kb-actions .el-button+.el-button{margin-left:0}.kb-empty{background:var(--app-soft, #f5f7ef);padding:25px;border-radius:9px;text-align:center;font-size:13px;color:var(--app-muted, #7b896c)}.kb-notice{color:var(--app-text, #367449);background:var(--app-soft, #edf5e8);border-radius:8px;padding:12px;font-size:12px}.kb-error{color:var(--app-danger, #a64536);background:var(--app-danger-bg, #fbefea);border-radius:8px;padding:12px;font-size:12px;line-height:1.8}@media(max-width:550px){.kb-form label{flex-basis:100%}.kb-list li{align-items:flex-start;flex-direction:column}.kb-heading{align-items:flex-start}.kb-actions{align-self:flex-end}}
@media(min-width:1100px){.kb-layout{display:grid;grid-template-columns:280px minmax(0,1fr);gap:24px}.kb-library{padding-right:20px;border-right:1px solid var(--app-border,#e4e9df)}.kb-form{flex-wrap:wrap}.kb-form label{min-width:0;flex-basis:100%}.kb-form .el-button{flex:1}.kb-list{max-height:400px}.kb-list li{flex-direction:column;align-items:stretch;padding:12px}.kb-actions{justify-content:flex-start}.kb-heading{align-items:flex-start}.kb-heading>div{min-width:0}.kb-heading .el-button{flex-shrink:0}.kb-hint{font-size:11px}}
</style>
