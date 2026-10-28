<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElTag } from 'element-plus'
import AccountPanel from './components/AccountPanel.vue'

const view = ref('home')
const views = { home: '知识库与问答', account: '账号与设置', service: '服务状态' }
const health = ref(null)
const loading = ref(false)
const error = ref('')
const checkedAt = ref('')
let controller
const connected = computed(() => health.value?.app === 'up' && health.value?.db === 'up')
const statusText = computed(() => loading.value ? '正在检查' : connected.value ? '服务连接正常' : error.value ? '暂时无法连接' : health.value ? '服务需要检查' : '等待检查')

async function refreshHealth() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), 8000)
  try {
    const response = await fetch('/api/health', { signal: controller.signal })
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const payload = await response.json()
    if (payload.code !== 0 || !payload.data || typeof payload.data.app !== 'string' || typeof payload.data.db !== 'string') {
      throw new Error('后端返回的健康检查格式不正确')
    }
    health.value = payload.data
  } catch (cause) {
    health.value = null
    error.value = cause.name === 'AbortError' ? '连接超时，请确认后端仍在运行。' : '未能读取后端状态，请确认后端服务仍在运行，然后重试。'
  } finally {
    clearTimeout(timeout)
    loading.value = false
    checkedAt.value = new Date().toLocaleTimeString('zh-CN', { hour12: false })
  }
}

onMounted(refreshHealth)
onUnmounted(() => controller?.abort())
</script>

<template>
  <div class="workspace">
    <aside class="sidebar">
      <a class="brand" href="#main" @click="view = 'home'" aria-label="MathRAG 工作台"><span class="brand-icon">M<span>·</span></span><span>MathRAG<small>数学知识 · 有据可循</small></span></a>
      <div class="section-label">工作空间</div>
      <nav class="workspace-nav" aria-label="工作空间">
        <button v-for="(label, key) in views" :key="key" type="button" class="workspace-link" :class="{ active: view === key }" :aria-current="view === key ? 'page' : undefined" @click="view = key">{{ label }}<span v-if="view === key" class="nav-dot" aria-hidden="true"></span></button>
      </nav>
      <div class="local-note"><span class="local-dot"></span> 本机工作空间</div>
    </aside>
    <main id="main">
      <header class="topbar"><span>工作空间 <span class="separator">/</span> {{ views[view] }}</span><span class="stage">MathRAG</span></header>
      <section class="page-heading"><h1>{{ views[view] }}</h1><p>{{ view === 'home' ? '选择知识库，开始有依据的数学对话。' : view === 'account' ? '管理登录账号和个人偏好。' : '查看连接情况与服务配置。' }}</p></section>
      <section v-show="view === 'service'" class="panel connection-panel" aria-labelledby="connection-title">
        <div class="panel-heading"><div><span class="eyebrow">01 / CONNECTION</span><h2 id="connection-title">服务连接</h2></div><ElButton :loading="loading" @click="refreshHealth">重新检查</ElButton></div>
        <div class="connection-status" aria-live="polite" :aria-busy="loading"><span class="status-light" :class="{ online: connected && !loading }"></span><div><strong>{{ statusText }}</strong><p>{{ loading ? '正在读取后端状态…' : error || (connected ? '前端已经可以与后端通信。' : '请根据下方状态检查后端服务。') }}</p></div><ElTag v-if="health" :type="health.llm?.mock ? 'warning' : 'info'" effect="plain">{{ health.llm?.mock ? '模拟模式' : '真实模型' }}</ElTag></div>
        <div class="metrics"><div><span>应用服务</span><strong>{{ health ? (health.app === 'up' ? '运行中' : '异常') : '—' }}</strong></div><div><span>数据库</span><strong>{{ health ? (health.db === 'up' ? '已连接' : '未连接') : '—' }}</strong></div><div><span>向量记录</span><strong>{{ typeof health?.vectors === 'number' ? health.vectors : '—' }}<small v-if="typeof health?.vectors === 'number'"> 条</small></strong></div><div><span>模型配置</span><strong>{{ health?.llm ? (health.llm.configured ? '已配置' : '尚未配置') : '—' }}</strong></div></div>
        <div class="panel-footer"><span>上次检查：{{ checkedAt || '尚未检查' }}</span><a href="/docs" target="_blank" rel="noopener noreferrer">打开接口文档 ↗</a></div>
      </section>

      <AccountPanel :view="view" @navigate="view = $event" />
    </main>
  </div>
</template>

<style scoped>
.workspace-nav{display:flex;flex-direction:column;gap:9px}.workspace-link{width:100%;display:flex;align-items:center;justify-content:space-between;text-align:left;padding:14px 16px;border:1px solid transparent;border-radius:9px;background:transparent;color:#c8dbd1;cursor:pointer;font-size:14px}.workspace-link:hover{background:#244c42}.workspace-link.active{background:#2b5145;border-color:#426759;color:#fff}.workspace-link:focus-visible{outline:2px solid #a4d2b2;outline-offset:3px}.local-note{margin-top:auto}.page-heading{margin:9px 0 24px}.page-heading h1{margin:0;font-size:27px;font-weight:600;letter-spacing:-.5px}.page-heading p{margin:9px 0 0;font-size:13px;color:var(--app-muted,#758473)}
</style>
