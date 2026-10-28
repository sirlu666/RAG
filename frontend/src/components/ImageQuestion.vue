<script setup>
import { computed, onBeforeUnmount, ref } from 'vue'
import { ElButton } from 'element-plus'
import { requestApi } from '../api.js'

const props = defineProps({ guest: Boolean, disabled: Boolean, csrfToken: String, appendText: Function })
const emit = defineEmits(['session-expired'])
const file = ref(null)
const preview = ref('')
const text = ref('')
const warnings = ref([])
const error = ref('')
const busy = ref(false)
const input = ref(null)
let controller
let revision = 0
const canConfirm = computed(() => !busy.value && !props.disabled && !!text.value.trim())

function cancel() {
  ++revision
  controller?.abort()
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = ''
  file.value = null
  text.value = ''
  warnings.value = []
  error.value = ''
  busy.value = false
  if (input.value) input.value.value = ''
}
async function recognize() {
  if (!file.value || props.guest || props.disabled || busy.value) return
  const version = ++revision
  controller = new AbortController()
  busy.value = true
  error.value = ''
  text.value = ''
  warnings.value = []
  const body = new FormData()
  body.append('file', file.value)
  try {
    const data = await requestApi('/api/chat/image/recognize', {
      method: 'POST', body, csrfToken: props.csrfToken, signal: controller.signal, timeoutMs: 180000,
    })
    if (version !== revision) return
    text.value = typeof data.text === 'string' ? data.text : ''
    if (!text.value.trim() && typeof data.latex === 'string') text.value = data.latex
    warnings.value = Array.isArray(data.warnings) ? data.warnings.filter(x => typeof x === 'string') : []
    if (!text.value.trim()) error.value = '未识别出有效文字，请手动补充或换图重试。'
  } catch (cause) {
    if (version !== revision || cause.status === -1) return
    error.value = cause.message
    if (cause.status === 401) emit('session-expired')
  } finally {
    if (version === revision) busy.value = false
  }
}
function select(event) {
  const selected = event.target.files?.[0]
  cancel()
  if (!selected) return
  if (!/\.(png|jpe?g|bmp|webp|tiff)$/i.test(selected.name) || !selected.size || selected.size > 10 * 1024 * 1024) {
    error.value = '请选择不超过 10MB 的 PNG、JPG、JPEG、BMP、WebP 或 TIFF 图片。'
    return
  }
  file.value = selected
  preview.value = URL.createObjectURL(selected)
  recognize()
}
function confirm() {
  if (canConfirm.value && props.appendText(text.value.trim())) cancel()
}
onBeforeUnmount(cancel)
</script>

<template>
  <section class="image-question" :aria-busy="busy">
    <p v-if="guest" class="image-hint">登录后可使用图片识题。</p>
    <template v-else>
      <div class="image-picker"><ElButton size="small" :disabled="disabled || busy" @click="input?.click()">选择题目图片</ElButton><input ref="input" hidden aria-label="图片识题" type="file" accept=".png,.jpg,.jpeg,.bmp,.webp,.tiff" :disabled="disabled || busy" @change="select"></div>
      <p class="image-hint">图片不加入知识库。识别后请校对，再加入草稿。</p>
      <div v-if="file" class="image-review">
        <img :src="preview" alt="待识别题目预览">
        <p>{{ file.name }}</p>
        <p v-if="busy" role="status">正在识别，请稍候…</p>
        <ul v-if="warnings.length"><li v-for="(warning, index) in warnings" :key="index">{{ warning }}</li></ul>
        <label>校对识别文本<textarea v-model="text" rows="5" :disabled="busy || disabled" /></label>
        <div class="image-actions"><ElButton size="small" :disabled="!canConfirm" @click="confirm">确认加入草稿</ElButton><ElButton size="small" :disabled="busy || disabled" @click="recognize">重新识别</ElButton><ElButton size="small" @click="cancel">取消图片</ElButton></div>
      </div>
    </template>
    <p v-if="error" class="image-error" role="alert">{{ error }}</p>
  </section>
</template>

<style scoped>
.image-question{margin-top:20px;font-size:12px}.image-picker{display:flex;align-items:center;gap:12px;flex-wrap:wrap}.image-hint{color:var(--app-muted, #73866a);line-height:1.8}.image-review{padding:14px;border:1px solid var(--app-border, #dce5d3);border-radius:9px;overflow-wrap:anywhere}.image-review img{display:block;max-width:100%;max-height:220px;object-fit:contain}.image-review label{display:flex;flex-direction:column;gap:8px}.image-review textarea{resize:vertical;font:inherit;line-height:1.8;padding:10px;border:1px solid var(--app-border, #dce5d3);border-radius:6px;background:var(--app-surface, #fff);color:var(--app-text, #304830)}.image-actions{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.image-actions .el-button{margin:0}.image-error{color:var(--app-danger, #a64536);line-height:1.8}
</style>
