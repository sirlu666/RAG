<script setup lang="ts">
/**
 * 对话页骨架（P1 起在此迭代）
 *
 * P1 待办：
 *  - [ ] 接入 MarkdownRenderer（markdown-it + KaTeX，公式先用占位符保护）
 *  - [ ] 引用面板：citation 事件 → 右侧卡片 → 点"原文"跳到 /docs/:id/preview#chunk
 *  - [ ] 会话列表（左栏）+ 新建/切换/删除
 *  - [ ] 停止生成：不做（SSE 无服务端语义，见 00 ADR-04）；只提供"重新生成"
 *  - [ ] 图片提问：范围外，已砍（见 06 §2）
 */
import { ref } from 'vue'
import { streamChat, type Citation } from '@/api/sse'

const question = ref('')
const answer = ref('')
const citations = ref<Citation[]>([])
const loading = ref(false)
const errorMsg = ref('')

async function send() {
  const q = question.value.trim()
  if (!q || loading.value) return
  loading.value = true
  errorMsg.value = ''
  answer.value = ''
  citations.value = []

  await streamChat(
    { question: q, kb_ids: ['public'], conversation_id: null },
    {
      onCitation: (c) => citations.value.push(c),
      // 此处直接赋值是为了跑通链路；P1 改成 buffer + requestAnimationFrame 批量 flush
      onDelta: (t) => (answer.value += t),
      onError: (e) => (errorMsg.value = e.message),
      onDone: () => (loading.value = false),
    },
  )
  loading.value = false
}
</script>

<template>
  <div class="chat-layout">
    <aside class="sidebar">
      <el-button type="primary" style="width: 100%">＋ 新对话</el-button>
      <p class="hint">会话列表（P2）</p>
    </aside>

    <section class="chat-main">
      <div class="messages">
        <div v-if="!answer && !loading" class="empty">
          <h2>把题目丢进来</h2>
          <p>登录后上传教材或讲义，提问时回答会标注依据，可跳原文。</p>
        </div>
        <div v-else class="bubble assistant">{{ answer }}</div>
        <el-alert v-if="errorMsg" :title="errorMsg" type="warning" :closable="false" />
      </div>

      <div class="composer">
        <el-input
          v-model="question"
          type="textarea"
          :rows="2"
          resize="none"
          placeholder="例如：求 f(x)=x²+2x 的单调区间（Enter 发送）"
          @keydown.enter.exact.prevent="send"
        />
        <el-button type="primary" :loading="loading" @click="send">发送</el-button>
      </div>
    </section>

    <aside class="citation-panel">
      <h3>参考依据</h3>
      <p v-if="!citations.length" class="hint">检索到的教材片段会显示在这里</p>
      <div v-for="c in citations" :key="c.chunk_id" class="citation">
        <div class="citation-head">
          <span class="idx">[{{ c.index }}]</span>
          <span class="doc">{{ c.doc_name }}</span>
          <span v-if="c.page" class="page">P{{ c.page }}</span>
        </div>
        <p class="snippet">{{ c.snippet }}</p>
      </div>
    </aside>
  </div>
</template>

<style scoped>
.chat-layout { display: flex; height: 100%; }
.sidebar { width: 240px; flex: none; padding: 16px; border-right: 1px solid #ebeef5; background: #fff; }
.chat-main { flex: 1; display: flex; flex-direction: column; min-width: 0; }
.messages { flex: 1; overflow-y: auto; padding: 24px; display: flex; flex-direction: column; gap: 12px; }
.empty { margin: auto; text-align: center; color: #6b7280; }
.empty h2 { margin-bottom: 8px; font-size: 20px; color: #1f2329; }
.bubble { background: #fff; border: 1px solid #ebeef5; border-radius: 12px; padding: 16px; white-space: pre-wrap; line-height: 1.8; }
.composer { flex: none; display: flex; gap: 12px; padding: 12px 24px 20px; }
.citation-panel { width: 320px; flex: none; padding: 16px; border-left: 1px solid #ebeef5; background: #fff; overflow-y: auto; }
.citation-panel h3 { font-size: 14px; color: #6b7280; margin: 0 0 12px; }
.citation { border: 1px solid #ebeef5; border-radius: 8px; padding: 10px; margin-bottom: 10px; }
.citation-head { display: flex; gap: 6px; font-size: 12px; color: #6b7280; }
.idx { color: #4b6cf5; font-weight: 600; }
.snippet { font-size: 13px; line-height: 1.7; margin: 6px 0 0; }
.hint { font-size: 12px; color: #b0b3b8; }
</style>
