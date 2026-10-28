<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { ElButton } from 'element-plus'
import { requestApi } from '../api.js'
import ChatPanel from './ChatPanel.vue'

const props = defineProps({ authenticated: Boolean, csrfToken: { type: String, default: '' }, revision: { type: Number, default: 0 } })
const emit = defineEmits(['session-expired'])
const items = ref([])
const selectedId = ref(null)
const loading = ref(false)
const error = ref('')
const selectedKb = computed(() => items.value.find(item => item.id === selectedId.value))
let controller
let generation = 0

async function load() {
  const version = ++generation
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const data = await requestApi('/api/public/kbs', { signal: controller.signal })
    if (version !== generation) return
    items.value = data
    if (!data.some(item => item.id === selectedId.value)) selectedId.value = null
  } catch (cause) {
    if (version === generation && cause.status !== -1) error.value = cause.message
  } finally { if (version === generation) loading.value = false }
}
watch(() => props.revision, load)
onMounted(load)
onBeforeUnmount(() => { ++generation; controller?.abort() })
</script>

<template>
  <section class="public-panel" aria-labelledby="public-title">
    <div class="public-heading"><h3 id="public-title">公共知识库 · {{ authenticated ? '登录问答' : '游客问答' }}</h3><ElButton size="small" :loading="loading" @click="load">刷新公共列表</ElButton></div>
    <p>只展示所有者明确公开的知识库。{{ authenticated ? '可提问、查看引用并保存自己的对话，资料修改权仍归所有者。' : '无需登录即可提问；登录后可查看引用和使用个人知识库。' }}</p>
    <p v-if="error" class="public-error" role="alert">{{ error }}</p>
    <p v-if="!loading && !error && !items.length">暂无公开知识库。请登录后创建只含公开练习资料的知识库，再点击“公开此库”。现有个人资料默认私有。</p>
    <div class="public-choices"><ElButton v-for="kb in items" :key="kb.id" size="small" :type="selectedId === kb.id ? 'primary' : 'default'" :aria-pressed="selectedId === kb.id" @click="selectedId = kb.id">{{ kb.name }}</ElButton></div>
    <ChatPanel v-if="selectedKb" :key="`${authenticated}-${selectedKb.id}`" :kb="selectedKb" :guest="!authenticated" :csrf-token="csrfToken" @session-expired="emit('session-expired')" />
  </section>
</template>

<style scoped>
.public-panel{border-top:1px solid var(--app-border, #dce5d3);padding-top:22px;margin-top:24px}.public-heading{display:flex;align-items:center;justify-content:space-between;gap:12px}.public-heading h3{font-size:17px;margin:0}.public-panel>p{font-size:12px;line-height:1.9;color:var(--app-muted, #73866a)}.public-choices{display:flex;gap:9px;flex-wrap:wrap;margin-top:15px}.public-choices .el-button+.el-button{margin-left:0}.public-panel .public-error{color:var(--app-danger, #a64536);background:var(--app-danger-bg, #fbefea);padding:12px}
</style>
