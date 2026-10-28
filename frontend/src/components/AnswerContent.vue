<script setup>
import { computed } from 'vue'
import DOMPurify from 'dompurify'
import { renderAnswerMarkdown } from '../answer-markdown.js'

const props = defineProps({ text: { type: String, default: '' } })
const html = computed(() => DOMPurify.sanitize(renderAnswerMarkdown(props.text), {
  USE_PROFILES: { html: true, svg: true },
  ADD_TAGS: ['mjx-container'],
  FORBID_TAGS: ['style', 'foreignObject', 'image', 'iframe', 'object'],
}))
</script>

<template><div class="answer-content" v-html="html"></div></template>

<style scoped>
.answer-content{font-size:14px;line-height:1.95;overflow-wrap:anywhere;color:var(--app-text, #304830)}.answer-content :deep(p){margin:10px 0}.answer-content :deep(h1),.answer-content :deep(h2),.answer-content :deep(h3){font-size:16px;margin:18px 0 9px}.answer-content :deep(pre){white-space:pre-wrap;background:var(--app-soft, #f1f4eb);padding:14px;border-radius:8px}.answer-content :deep(table){border-collapse:collapse;display:block;overflow:auto}.answer-content :deep(td),.answer-content :deep(th){border:1px solid var(--app-border, #dce4d4);padding:8px}.answer-content :deep(mjx-container){max-width:100%;overflow-x:auto;overflow-y:hidden;display:inline-block;vertical-align:middle}.answer-content :deep(mjx-container[display="true"]){display:block;text-align:center;padding:10px 0}.answer-content :deep(svg){max-width:none}.answer-content :deep(a){color:var(--app-text, #2b775b);text-decoration:underline}
</style>
