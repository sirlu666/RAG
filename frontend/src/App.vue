<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { ElButton, ElTag } from 'element-plus'
import AccountPanel from './components/AccountPanel.vue'

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
    error.value = cause.name === 'AbortError' ? '连接超时，请确认后端仍在运行。' : '未能读取后端状态，请确认后端已在 8000 端口启动，然后重试。'
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
      <a class="brand" href="#main" aria-label="MathRAG 工作台"><span class="brand-icon">M<span>·</span></span><span>MathRAG<small>数学知识 · 有据可循</small></span></a>
      <div class="section-label">工作空间</div>
      <div class="current-section"><span aria-hidden="true">◈</span> 项目概览 <span class="nav-dot"></span></div>
      <div class="sidebar-note"><span class="section-label">学习与探索</span><p>从一道题出发，<br>让每一步推导都有依据。</p><div class="equation" aria-hidden="true">f′(x) → 思路 → 解答</div></div>
      <div class="local-note"><span class="local-dot"></span> 本机工作空间</div>
    </aside>

    <main id="main">
      <header class="topbar"><span>工作空间 <span class="separator">/</span> 项目概览</span><span class="stage">本机工作台</span></header>
      <section class="hero">
        <div><div class="eyebrow">MATHEMATICS, WITH CONTEXT</div><h1>数学答疑工作台<span>从理解问题，到找到依据。</span></h1><p class="hero-description">连接数学资料与解题思路，逐步建立你的个人知识空间。</p></div>
        <div class="math-art" aria-hidden="true"><span class="art-caption">EXPLORE · REASON · LEARN</span><span class="formula">∫ f(x) dx</span><div class="art-line"></div><span class="art-footer">每一个答案，都有来处。</span></div>
      </section>

      <section class="panel connection-panel" aria-labelledby="connection-title">
        <div class="panel-heading"><div><span class="eyebrow">01 / CONNECTION</span><h2 id="connection-title">服务连接</h2></div><ElButton :loading="loading" @click="refreshHealth">重新检查</ElButton></div>
        <div class="connection-status" aria-live="polite" :aria-busy="loading"><span class="status-light" :class="{ online: connected && !loading }"></span><div><strong>{{ statusText }}</strong><p>{{ loading ? '正在读取后端状态…' : error || (connected ? '前端已经可以与后端通信。' : '请根据下方状态检查后端服务。') }}</p></div><ElTag v-if="health" :type="health.llm?.mock ? 'warning' : 'info'" effect="plain">{{ health.llm?.mock ? '模拟模式' : '模型模式待验收' }}</ElTag></div>
        <div class="metrics"><div><span>应用服务</span><strong>{{ health ? (health.app === 'up' ? '运行中' : '异常') : '—' }}</strong></div><div><span>数据库</span><strong>{{ health ? (health.db === 'up' ? '已连接' : '未连接') : '—' }}</strong></div><div><span>向量记录</span><strong>{{ typeof health?.vectors === 'number' ? health.vectors : '—' }}<small v-if="typeof health?.vectors === 'number'"> 条</small></strong></div><div><span>模型配置</span><strong>{{ health?.llm ? (health.llm.configured ? '已配置' : '尚未配置') : '—' }}</strong></div></div>
        <div class="panel-footer"><span>上次检查：{{ checkedAt || '尚未检查' }}</span><a href="http://127.0.0.1:8000/docs" target="_blank" rel="noopener noreferrer">打开接口文档 ↗</a></div>
      </section>

      <AccountPanel />

      <div class="lower-grid"><section class="panel next-panel"><span class="eyebrow">03 / QUICK GUIDE</span><h2>使用指南</h2><ol><li><span>01</span><div><h3>管理学习资料</h3><p>创建个人知识库，拖拽上传文档或图片，预览、校对并管理资料。</p></div></li><li><span>02</span><div><h3>提问与查看依据</h3><p>选择知识库后提问；登录后可查看引用片段和原文件，也可恢复历史对话继续追问。</p></div></li><li><span>03</span><div><h3>设置个人空间</h3><p>在个人设置中修改昵称、头像、主题和字体，保存后随账号保留。</p></div></li></ol></section>
        <section class="learning-note"><span class="eyebrow">使用提示</span><h2>结合原文，<br>核对每一步思路。</h2><p>通过回答下方的引用片段查看对应正文，结合原文件核对题意和公式。</p><p>图片识别结果可以人工校对后保存。若显示“模拟模式”，回答仅用于演示交互，不作为解题依据。</p><span class="note-marker" aria-hidden="true">↗</span></section></div>
      <footer class="page-footer">MathRAG · 个人数学知识与答疑平台<span>资料管理 · 问答与引用 · 个人设置</span></footer>
    </main>
  </div>
</template>
