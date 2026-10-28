<script setup>
import { computed, onBeforeUnmount, onMounted, ref, useId } from 'vue'
import { ElButton, ElProgress, ElTag } from 'element-plus'
import { requestApi, uploadDocument } from '../api.js'
import { fileProblem, newUploadId, runUploadQueue } from '../document-upload.js'
import DocumentTextEditor from './DocumentTextEditor.vue'
import DocumentMetadataEditor from './DocumentMetadataEditor.vue'
import DocumentReplacementEditor from './DocumentReplacementEditor.vue'
import { filterDocuments, hasAutoTags } from '../document-filter.js'

const props = defineProps({ kb: { type: Object, required: true }, csrfToken: { type: String, required: true } })
const emit = defineEmits(['session-expired', 'documents-changed', 'uploading-change'])
const documents = ref([])
const loaded = ref(false)
const loading = ref(false)
const uploading = ref(false)
const deletingId = ref(null)
const editorDoc = ref(null)
const editorMode = ref('text')
const query = ref('')
const categoryFilter = ref(null)
const knowledgePointFilter = ref(null)
const questionTypeFilter = ref(null)
const difficultyFilter = ref(null)
const tagStatusFilter = ref('all')
const tagFilterId = useId()
const queue = ref([])
const dragging = ref(false)
const fileInput = ref(null)
const cameraInput = ref(null)
const error = ref('')
const notice = ref('')
const progressError = ref('')
const progress = ref({})
const pollingEnabled = ref(true)
const previewDoc = ref(null)
const previewData = ref(null)
const previewLoading = ref(false)
const previewError = ref('')
const previewPage = ref(1)
const lifetime = new AbortController()
let alive = true
let revision = 0
let previewRevision = 0
let pollTimer
let pollController
let previewController

const pendingStates = new Set(['pending', 'parsing', 'embedding'])
const pending = computed(() => documents.value.filter(doc => pendingStates.has(doc.status)))
const filteredDocuments = computed(() => filterDocuments(documents.value, query.value, categoryFilter.value, {
  knowledgePoint: knowledgePointFilter.value, questionType: questionTypeFilter.value,
  difficulty: difficultyFilter.value, tagStatus: tagStatusFilter.value,
}))
const knowledgePoints = computed(() => labelOptions('knowledge_points', knowledgePointFilter.value))
const questionTypes = computed(() => labelOptions('question_types', questionTypeFilter.value))
const categories = computed(() => [...new Set(['', ...documents.value.map(doc => doc.category || ''), ...(categoryFilter.value === null ? [] : [categoryFilter.value])])].sort((a, b) => a.localeCompare(b, 'zh-CN')))
const queuedCount = computed(() => queue.value.filter(item => item.status === 'queued').length)
const uploadNames = { queued: '等待上传', uploading: '正在传输', accepted: '已受理', invalid: '无法上传', failed: '上传失败', cancelled: '已取消' }
const stateNames = { pending: '排队中', parsing: '解析中', embedding: '向量化中', ready: '已就绪', rejected: '内容不符合要求', failed: '处理失败' }
const typeNames = { concept: '知识概念', example: '例题', exercise: '习题', theory: '定理', definition: '定义', caption: '题注', other: '正文' }

function labelOptions(field, selected) {
  return [...new Set([...documents.value.flatMap(doc => doc[field] || []), ...(selected ? [selected] : [])])]
    .sort((a, b) => a.localeCompare(b, 'zh-CN'))
}

function clearFilters() {
  query.value = ''
  categoryFilter.value = null
  knowledgePointFilter.value = null
  questionTypeFilter.value = null
  difficultyFilter.value = null
  tagStatusFilter.value = 'all'
}

function report(cause) {
  if (!alive || cause.status === -1) return
  error.value = cause.message
  if (cause.status === 401) emit('session-expired')
}

function stopPolling() {
  clearTimeout(pollTimer)
  pollController?.abort()
}

function schedulePoll(version) {
  if (alive && pollingEnabled.value && pending.value.length && version === revision) {
    pollTimer = setTimeout(() => pollStatuses(version), 1500)
  }
}

async function pollStatuses(version) {
  pollController = new AbortController()
  const signal = AbortSignal.any([lifetime.signal, pollController.signal])
  try {
    const updates = await Promise.all(pending.value.map(async doc => ({
      id: doc.id, state: await requestApi(`/api/docs/${doc.id}/status`, { signal }),
    })))
    if (!alive || version !== revision) return
    for (const { id, state } of updates) {
      progress.value[id] = state.progress
      const doc = documents.value.find(item => item.id === id)
      if (doc) Object.assign(doc, { status: state.status, chunk_count: state.chunk_count, error_msg: state.error })
    }
    progressError.value = ''
    schedulePoll(version)
  } catch (cause) {
    if (!alive || version !== revision || cause.status === -1) return
    if (cause.status === 401) emit('session-expired')
    else progressError.value = `${cause.message} 自动查询已暂停，点击“刷新文档”重试。`
  }
}

async function loadDocuments() {
  if (loading.value || !alive) return
  const version = ++revision
  stopPolling()
  loading.value = true
  error.value = ''
  progressError.value = ''
  pollingEnabled.value = true
  try {
    const data = await requestApi(`/api/docs?kb_id=${encodeURIComponent(props.kb.id)}`, { signal: lifetime.signal })
    if (!alive || version !== revision) return
    documents.value = data
    progress.value = {}
    loaded.value = true
  } catch (cause) {
    report(cause)
    loaded.value = false
  } finally {
    if (alive && version === revision) {
      loading.value = false
      schedulePoll(version)
    }
  }
}

function togglePolling() {
  pollingEnabled.value = !pollingEnabled.value
  stopPolling()
  if (pollingEnabled.value) schedulePoll(revision)
}

function addFiles(files) {
  if (uploading.value || loading.value || deletingId.value || editorDoc.value) return
  for (const file of Array.from(files || [])) {
    if (queue.value.some(item => item.file.name === file.name && item.file.size === file.size && item.file.lastModified === file.lastModified)) continue
    const problem = fileProblem(file)
    queue.value.push({ id: newUploadId(), file, percent: 0, status: problem ? 'invalid' : 'queued', error: problem, docId: null })
  }
  error.value = ''
  notice.value = ''
  if (fileInput.value) fileInput.value.value = ''
}

function dropFiles(event) {
  dragging.value = false
  addFiles(event.dataTransfer?.files)
}

function addPhoto(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || uploading.value || loading.value || deletingId.value || editorDoc.value) return
  const extension = ({ 'image/jpeg': 'jpg', 'image/png': 'png' })[file.type]
    || file.name.match(/\.(png|jpe?g)$/i)?.[1]?.toLowerCase()
  if (!extension) {
    error.value = '照片需为 PNG、JPG 或 JPEG 格式；请将 HEIC 等照片转换后再选择。'
    return
  }
  const photo = new File([file], `拍照-${Date.now()}-${newUploadId().slice(0, 8)}.${extension}`, {
    type: file.type, lastModified: file.lastModified,
  })
  addFiles([photo])
  notice.value = '照片已加入队列，请点击上传。就绪后可预览正文并校对识别文字。'
}

function uploadState(item) {
  if (item.status !== 'accepted') return uploadNames[item.status]
  const doc = documents.value.find(doc => doc.id === item.docId)
  return doc ? `已受理 · ${stateNames[doc.status] || doc.status}` : '已受理 · 请以下方文档列表为准'
}

async function upload() {
  if (uploading.value || loading.value || deletingId.value || editorDoc.value || !queuedCount.value) return
  uploading.value = true
  emit('uploading-change', true)
  error.value = ''
  notice.value = ''
  try {
    await runUploadQueue(queue.value, (file, onProgress) => uploadDocument(file, props.kb.id, props.csrfToken, {
      signal: lifetime.signal, onProgress,
    }), {
      signal: lifetime.signal,
      onAccepted: async () => {
        if (!alive) return
        emit('documents-changed')
        await loadDocuments()
      },
      onError: cause => { if (cause.status === 401) report(cause) },
    })
    if (!alive) return
    notice.value = '本轮传输结束。每个文件的结果见队列；解析进度见文档列表。失败项不会自动重试，请先刷新列表核对，再清除队列重新选择。'
  } catch (cause) {
    report(cause)
  } finally {
    if (alive) {
      uploading.value = false
      emit('uploading-change', false)
    }
  }
}

async function removeDocument(doc) {
  if (uploading.value || loading.value || deletingId.value || editorDoc.value || pendingStates.has(doc.status)) return
  if (!window.confirm(`确定删除资料「${doc.filename}」？\n将删除服务器保存的文件、旧版备份、正文片段及检索索引，无法直接撤销。\n你的本机原文件和其他资料保留。历史回答仍保留，但其对应正文将无法打开。`)) return
  deletingId.value = doc.id
  emit('uploading-change', true)
  stopPolling()
  error.value = ''
  notice.value = ''
  try {
    await requestApi(`/api/docs/${encodeURIComponent(doc.id)}`, {
      method: 'DELETE', csrfToken: props.csrfToken, signal: lifetime.signal,
    })
    if (!alive) return
    if (previewDoc.value?.id === doc.id) closePreview()
    queue.value = queue.value.filter(item => item.docId !== doc.id)
    notice.value = `已删除「${doc.filename}」。本机原文件保留。`
    emit('documents-changed')
    await loadDocuments()
  } catch (cause) {
    report(cause)
    if (alive && cause.status !== 401 && cause.status !== -1) {
      error.value += ' 请刷新文档列表核对当前状态；不要连续重复删除。'
    }
  } finally {
    if (alive) {
      deletingId.value = null
      emit('uploading-change', false)
      stopPolling()
      schedulePoll(revision)
    }
  }
}

function editText(doc, mode = 'text') {
  if (uploading.value || loading.value || deletingId.value || editorDoc.value) return
  closePreview()
  stopPolling()
  editorMode.value = mode
  editorDoc.value = doc
  emit('uploading-change', true)
}

function closeEditor() {
  editorDoc.value = null
  emit('uploading-change', false)
  stopPolling()
  schedulePoll(revision)
}

async function textSaved() {
  closePreview()
  closeEditor()
  notice.value = '正文与索引已更新，旧版已备份。请重新打开预览，检查新内容。'
  await loadDocuments()
}

async function metadataSaved() {
  closePreview()
  closeEditor()
  notice.value = '名称与分类已保存。新问答引用将使用新名称；历史回答保持原样。'
  await loadDocuments()
}

async function replacementSaved(result) {
  closePreview()
  closeEditor()
  notice.value = result.changed ? '新版本与索引已更新，旧版已备份。资料名称和分类保留，请重新预览核对。' : '新文件与当前版本相同，无需替换。'
  await loadDocuments()
}

function closePreview() {
  ++previewRevision
  previewController?.abort()
  previewDoc.value = null
  previewData.value = null
  previewError.value = ''
  previewLoading.value = false
}

async function preview(doc, page = 1) {
  const version = ++previewRevision
  previewController?.abort()
  previewController = new AbortController()
  previewDoc.value = doc
  previewPage.value = page
  previewData.value = null
  previewError.value = ''
  previewLoading.value = true
  try {
    const data = await requestApi(`/api/docs/${doc.id}/preview?page=${page}&size=5`, {
      signal: AbortSignal.any([lifetime.signal, previewController.signal]),
    })
    if (alive && version === previewRevision) previewData.value = data
  } catch (cause) {
    if (!alive || version !== previewRevision || cause.status === -1) return
    previewError.value = cause.message
    if (cause.status === 401) emit('session-expired')
  } finally {
    if (alive && version === previewRevision) previewLoading.value = false
  }
}

onMounted(loadDocuments)
onBeforeUnmount(() => {
  emit('uploading-change', false)
  alive = false
  ++revision
  ++previewRevision
  stopPolling()
  previewController?.abort()
  lifetime.abort()
})
</script>

<template>
  <section class="doc-panel" aria-labelledby="docs-title">
    <div class="doc-heading"><div><h3 id="docs-title">{{ kb.name }} · 资料</h3><p>上传文档后，系统会解析并整理成可检索的片段。</p></div><ElButton size="small" :loading="loading" :disabled="uploading || !!deletingId || !!editorDoc" @click="loadDocuments">刷新文档</ElButton></div>
    <form class="doc-upload" @submit.prevent="upload">
      <label for="doc-file" class="drop-zone" :class="{ dragging }" @dragover.prevent="dragging = !uploading && !loading && !deletingId && !editorDoc" @dragleave.prevent="dragging = false" @drop.prevent="dropFiles">
        选择多份数学资料，或将文件拖到这里
        <input id="doc-file" ref="fileInput" type="file" multiple accept=".pdf,.docx,.md,.txt,.png,.jpg,.jpeg" :disabled="uploading || loading || !!deletingId || !!editorDoc" @change="addFiles($event.target.files)" />
      </label>
      <input ref="cameraInput" type="file" accept="image/jpeg,image/png" capture="environment" hidden :disabled="uploading || loading || !!deletingId || !!editorDoc" aria-label="拍摄或选择一道数学题的照片" @change="addPhoto" />
      <ElButton native-type="button" :disabled="uploading || loading || !!deletingId || !!editorDoc" @click="cameraInput?.click()">拍照识题</ElButton>
      <ElButton type="primary" native-type="submit" :loading="uploading" :disabled="loading || !!deletingId || !!editorDoc || !queuedCount">上传 {{ queuedCount }} 份资料</ElButton>
      <ElButton v-if="queue.length" :disabled="uploading || !!deletingId || !!editorDoc" @click="queue = []">清除队列</ElButton>
      <p>支持 PDF、DOCX、MD、TXT、PNG、JPG、JPEG，单文件最多 50MB。图片使用本地文字 OCR，数学公式识别可能不准确。按顺序传输，不自动覆盖原资料。</p>
      <p>拍照识题：支持的手机浏览器可调用后置相机，电脑通常打开图片选择窗口。拍摄后先加入队列，再由你确认上传；取消选择不会上传。尽量拍清文字、摆正题目并避开反光。</p>
    </form>
    <ul v-if="queue.length" class="upload-queue" aria-label="批量上传队列" aria-live="polite">
      <li v-for="item in queue" :key="item.id">
        <div><strong>{{ item.file.name }}</strong><span>{{ uploadState(item) }}</span></div>
        <ElProgress v-if="['uploading', 'accepted'].includes(item.status)" :percentage="item.percent" :stroke-width="5" />
        <small v-if="item.status === 'uploading'">{{ item.percent === 100 ? '文件已传输，等待服务器确认。' : '传输进度不代表解析完成。' }}</small>
        <p v-if="item.error" class="file-error">{{ item.error }}</p>
      </li>
    </ul>
    <p v-if="notice" class="doc-notice" role="status">{{ notice }}</p><p v-if="error" class="doc-error" role="alert">{{ error }}</p><p v-if="progressError" class="doc-error" role="alert">{{ progressError }}</p>
    <div v-if="pending.length" class="poll-control"><span>{{ pending.length }} 份资料仍在处理。离开此知识库不会停止服务器解析。</span><ElButton size="small" @click="togglePolling">{{ pollingEnabled ? '暂停自动查询' : '继续自动查询' }}</ElButton></div>
    <p v-if="loading" class="doc-hint" role="status">正在读取文档列表…</p><p v-else-if="loaded && !documents.length" class="doc-empty">此知识库暂无资料。可以先上传“数学上传练习.txt”。</p>
    <div v-if="loaded && documents.length" class="doc-filters">
      <label for="doc-search">按名称查找<input id="doc-search" v-model="query" type="search" placeholder="输入资料名称" /></label>
      <label for="doc-filter-category">手动分类<select id="doc-filter-category" v-model="categoryFilter"><option :value="null">全部分类</option><option v-for="name in categories" :key="name" :value="name">{{ name || '未分类' }}</option></select></label>
      <label :for="`${tagFilterId}-knowledge`">自动知识点<select :id="`${tagFilterId}-knowledge`" v-model="knowledgePointFilter"><option :value="null">全部知识点</option><option v-for="name in knowledgePoints" :key="name" :value="name">{{ name }}</option></select></label>
      <label :for="`${tagFilterId}-type`">自动题型<select :id="`${tagFilterId}-type`" v-model="questionTypeFilter"><option :value="null">全部题型</option><option v-for="name in questionTypes" :key="name" :value="name">{{ name }}</option></select></label>
      <label :for="`${tagFilterId}-difficulty`">自动难度<select :id="`${tagFilterId}-difficulty`" v-model="difficultyFilter"><option :value="null">全部难度</option><option v-for="name in ['基础', '进阶', '困难']" :key="name" :value="name">{{ name }}</option></select></label>
      <label :for="`${tagFilterId}-status`">自动标签状态<select :id="`${tagFilterId}-status`" v-model="tagStatusFilter"><option value="all">全部状态</option><option value="tagged">已有标签</option><option value="untagged">未标注</option></select></label>
      <ElButton size="small" @click="clearFilters">清除筛选</ElButton>
      <span role="status">显示 {{ filteredDocuments.length }} / {{ documents.length }} 份资料</span>
    </div>
    <p v-if="loaded && documents.length" class="doc-hint">自动标签显示已有标注结果。筛选只影响资料列表，问答仍使用所选知识库。</p>
    <p v-if="loaded && documents.length && !filteredDocuments.length" class="doc-hint">没有符合筛选条件的资料，请调整名称、分类或自动标签。资料仍保留在知识库中。</p>
    <ul v-if="loaded && filteredDocuments.length" class="doc-list"><li v-for="doc in filteredDocuments" :key="doc.id"><div class="doc-info"><strong>{{ doc.filename }}</strong><div class="doc-meta"><ElTag size="small" :type="doc.status === 'ready' ? 'success' : ['failed','rejected'].includes(doc.status) ? 'danger' : 'info'">{{ stateNames[doc.status] || doc.status }}</ElTag><span>{{ doc.category || '未分类' }}</span><span>{{ doc.chunk_count }} 个片段 · {{ Math.ceil(doc.size_bytes / 1024) }} KB</span></div><div class="doc-auto-tags" aria-label="自动知识标签"><template v-if="hasAutoTags(doc)"><span v-if="doc.knowledge_points?.length">知识点：</span><ElTag v-for="label in doc.knowledge_points" :key="`point-${label}`" size="small" effect="plain">{{ label }}</ElTag><span v-if="doc.question_types?.length">题型：</span><ElTag v-for="label in doc.question_types" :key="`type-${label}`" size="small" type="info" effect="plain">{{ label }}</ElTag><ElTag v-if="doc.difficulty" size="small" type="warning" effect="plain">难度：{{ doc.difficulty }}</ElTag></template><span v-else>自动标签：未标注（或暂无有效标签）</span></div><ElProgress v-if="pendingStates.has(doc.status)" :percentage="progress[doc.id] ?? 0" :stroke-width="5" /><p v-if="doc.error_msg" class="file-error">{{ doc.error_msg }}</p></div><div class="doc-actions"><ElButton size="small" :disabled="uploading || loading || !!deletingId || !!editorDoc || pendingStates.has(doc.status)" @click="editText(doc, 'replacement')">替换新版本</ElButton><ElButton size="small" :disabled="uploading || loading || !!deletingId || !!editorDoc || pendingStates.has(doc.status)" @click="editText(doc, 'metadata')">名称与分类</ElButton><ElButton v-if="['txt', 'md', 'png', 'jpg', 'jpeg'].includes(doc.file_type)" size="small" :disabled="uploading || loading || !!deletingId || !!editorDoc || pendingStates.has(doc.status)" @click="editText(doc)">{{ ['png', 'jpg', 'jpeg'].includes(doc.file_type) ? '校对识别文字' : '编辑正文' }}</ElButton><ElButton size="small" :disabled="doc.status !== 'ready'" :aria-label="`预览：${doc.filename}`" @click="preview(doc)">预览正文</ElButton><ElButton size="small" type="danger" plain :loading="deletingId === doc.id" :disabled="uploading || loading || !!deletingId || !!editorDoc || pendingStates.has(doc.status)" :title="pendingStates.has(doc.status) ? '请等待处理结束后再删除' : '删除前需确认'" :aria-label="`删除：${doc.filename}`" @click="removeDocument(doc)">删除</ElButton></div></li></ul>
    <DocumentReplacementEditor v-if="editorDoc && editorMode === 'replacement'" :doc="editorDoc" :csrf-token="csrfToken" @close="closeEditor" @saved="replacementSaved" @session-expired="emit('session-expired')" />
    <DocumentMetadataEditor v-if="editorDoc && editorMode === 'metadata'" :doc="editorDoc" :csrf-token="csrfToken" :categories="categories" @close="closeEditor" @saved="metadataSaved" @session-expired="emit('session-expired')" />
    <DocumentTextEditor v-if="editorDoc && editorMode === 'text'" :doc="editorDoc" :csrf-token="csrfToken" @close="closeEditor" @saved="textSaved" @session-expired="emit('session-expired')" />
    <section v-if="previewDoc" class="doc-preview" aria-labelledby="preview-title" :aria-busy="previewLoading"><div class="doc-heading"><div><h4 id="preview-title">{{ previewDoc.filename }}</h4><p>解析后的正文片段，不是原文件的版式预览。</p></div><ElButton size="small" @click="closePreview">关闭预览</ElButton></div><p v-if="previewLoading" role="status">正在读取正文…</p><p v-if="previewError" class="doc-error" role="alert">{{ previewError }}</p><template v-if="previewData"><p class="doc-hint">共 {{ previewData.total }} 个片段 · 第 {{ previewData.page }} 页</p><article v-for="chunk in previewData.items" :key="chunk.id" class="doc-chunk"><div>{{ typeNames[chunk.content_type] || chunk.content_type }} · 片段 {{ chunk.seq + 1 }}<span v-if="chunk.page"> · 原文第 {{ chunk.page }} 页</span></div><pre>{{ chunk.content }}</pre></article><p v-if="!previewData.items.length" class="doc-hint">本页没有片段。</p></template><div class="preview-pagination"><ElButton size="small" :disabled="previewLoading || previewPage <= 1" @click="preview(previewDoc, previewPage - 1)">上一页</ElButton><ElButton v-if="previewError" size="small" @click="preview(previewDoc, previewPage)">重试预览</ElButton><ElButton size="small" :disabled="previewLoading || !previewData || previewPage * 5 >= previewData.total" @click="preview(previewDoc, previewPage + 1)">下一页</ElButton></div></section>
  </section>
</template>

<style scoped>
.doc-filters{display:flex;gap:12px;align-items:end;flex-wrap:wrap;margin-top:20px;font-size:12px;color:var(--app-text, #61745b)}.doc-filters label{display:flex;flex-direction:column;gap:6px;max-width:100%}.doc-filters input,.doc-filters select{box-sizing:border-box;max-width:100%;padding:8px;border:1px solid var(--app-border, #bfcfb2);border-radius:6px;font:inherit;background:var(--app-surface, #fff)}.doc-filters input:focus,.doc-filters select:focus{outline:2px solid var(--app-accent, #367449)}.doc-filters span{align-self:center}
.doc-auto-tags{display:flex;align-items:center;flex-wrap:wrap;gap:6px;margin:9px 0;font-size:11px;color:var(--app-muted, #7c8a73)}
.doc-actions{display:flex;gap:8px;flex-wrap:wrap}.doc-actions .el-button+.el-button{margin-left:0}
.drop-zone{padding:14px;border:1px dashed var(--app-border, #bfcfb2);border-radius:8px;background:var(--app-surface, #fff)}.drop-zone.dragging{background:var(--app-soft, #edf5e8);border-color:var(--app-accent, #367449)}.upload-queue{list-style:none;padding:0;margin:16px 0;font-size:12px}.upload-queue li{padding:12px;background:var(--app-surface, #fff);border:1px solid var(--app-border, #e1e8da);border-radius:8px;margin-top:8px}.upload-queue li>div:first-child{display:flex;justify-content:space-between;gap:12px;margin-bottom:8px;flex-wrap:wrap}.upload-queue strong{overflow-wrap:anywhere;min-width:0}.upload-queue span,.upload-queue small{color:var(--app-muted, #7c8a73)}
.doc-panel{margin-top:22px;padding:23px;border:1px solid var(--app-border, #dce5d3);border-radius:12px;background:var(--app-soft, #f9fbf6)}.doc-heading{display:flex;gap:15px;align-items:center;justify-content:space-between}.doc-heading h3,.doc-heading h4{margin:0;font-size:16px;overflow-wrap:anywhere}.doc-heading h4{font-size:14px}.doc-heading p,.doc-hint,.doc-upload p{font-size:12px;color:var(--app-muted, #7c8a73);line-height:1.8;margin:7px 0}.doc-upload{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin-top:20px}.doc-upload label{flex:1;min-width:180px;display:flex;gap:9px;flex-direction:column;font-size:12px}.doc-upload input{font:inherit;max-width:100%;padding:10px;border:1px dashed var(--app-border, #bfcfb2);border-radius:8px;background:var(--app-surface, #fff)}.doc-upload p{flex-basis:100%;margin:0}.doc-upload .el-button{height:39px}.upload-progress{font-size:12px;margin-top:18px;line-height:1.8}.upload-progress small{color:var(--app-muted, #7c8a73)}.doc-notice{background:var(--app-soft, #edf5e8);color:var(--app-text, #367449);padding:12px;border-radius:8px;font-size:12px;line-height:1.8}.doc-error{background:var(--app-danger-bg, #fbefea);color:var(--app-danger, #a64536);padding:12px;border-radius:8px;font-size:12px;line-height:1.8}.doc-empty{font-size:12px;color:var(--app-muted, #7c8a73);margin:20px 0}.doc-list{list-style:none;padding:0;margin:20px 0 0}.doc-list li{display:flex;align-items:center;justify-content:space-between;gap:12px;padding:16px 0;border-top:1px solid var(--app-border, #e0e8d8)}.doc-info{flex:1;min-width:0}.doc-info strong{font-size:13px;overflow-wrap:anywhere;font-weight:550}.doc-meta{display:flex;gap:10px;align-items:center;margin:9px 0;color:var(--app-muted, #7c8a73);font-size:11px;flex-wrap:wrap}.file-error{color:var(--app-danger, #a64536);font-size:12px;overflow-wrap:anywhere}.poll-control{display:flex;align-items:center;gap:12px;justify-content:space-between;font-size:11px;color:var(--app-muted, #7c8a73);margin-top:16px}.doc-preview{border-top:1px solid var(--app-border, #dce5d3);padding-top:22px;margin-top:22px}.doc-chunk{background:var(--app-surface, #fff);border:1px solid var(--app-border, #e1e8da);border-radius:8px;margin:12px 0;padding:16px}.doc-chunk>div{font-size:11px;color:var(--app-muted, #7c8a73)}.doc-chunk pre{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.9 var(--app-font, "Segoe UI","Microsoft YaHei",sans-serif);color:var(--app-text, #304830);margin:12px 0 0}.preview-pagination{display:flex;gap:8px;flex-wrap:wrap;margin-top:16px}.preview-pagination .el-button+.el-button{margin-left:0}@media(max-width:550px){.doc-panel{padding:15px}.doc-heading{align-items:flex-start}.doc-upload{align-items:stretch}.doc-upload label{flex-basis:100%}.poll-control{align-items:flex-start;flex-direction:column}.doc-list li{flex-wrap:wrap}.doc-heading .el-button{flex-shrink:0}}
</style>
