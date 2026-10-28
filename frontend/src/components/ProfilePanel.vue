<script setup>
import { computed, onBeforeUnmount, ref, useId, watch } from 'vue'
import { ElButton } from 'element-plus'
import { requestApi } from '../api.js'

const props = defineProps({ user: { type: Object, required: true }, csrfToken: { type: String, required: true }, disabled: Boolean })
const emit = defineEmits(['saved', 'session-expired', 'busy-change'])
const inputId = useId()
const nickname = ref(props.user.nickname || '')
const saving = ref(false)
const notice = ref('')
const error = ref('')
const dirty = computed(() => nickname.value.trim() !== (props.user.nickname || ''))
const lifetime = new AbortController()
const avatarInputId = useId()
const avatarFile = ref(null)
const avatarPreview = ref('')
const themeInputId = useId()
const theme = ref(props.user.theme || 'default')
const fontInputId = useId()
const font = ref(props.user.font || 'default')
const previewFont = computed(() => ({
  song: 'SimSun, "Songti SC", serif',
  kai: 'KaiTi, STKaiti, serif',
}[font.value] || 'Inter, "Segoe UI", "Microsoft YaHei", sans-serif'))
watch(() => props.user.font, value => { font.value = value || 'default' })
watch(() => props.user.theme, value => { theme.value = value || 'default' })

async function saveFont() {
  if (saving.value || props.disabled || font.value === (props.user.font || 'default')) return
  saving.value = true
  emit('busy-change', true)
  notice.value = ''
  error.value = ''
  try {
    const data = await requestApi('/api/auth/me/font', {
      method: 'PATCH', body: { font: font.value }, csrfToken: props.csrfToken, signal: lifetime.signal,
    })
    emit('saved', data.user)
    notice.value = '字体已保存并应用。'
  } catch (cause) {
    if (cause.status === -1) return
    error.value = cause.message
    if (cause.status === 0) error.value += ' 请刷新页面核对已保存的字体。'
    if (cause.status === 401) emit('session-expired')
  } finally {
    saving.value = false
    emit('busy-change', false)
  }
}

async function saveTheme() {
  if (saving.value || props.disabled || theme.value === (props.user.theme || 'default')) return
  saving.value = true
  emit('busy-change', true)
  notice.value = ''
  error.value = ''
  try {
    const data = await requestApi('/api/auth/me/theme', {
      method: 'PATCH', body: { theme: theme.value }, csrfToken: props.csrfToken, signal: lifetime.signal,
    })
    emit('saved', data.user)
    notice.value = '主题已保存并应用。'
  } catch (cause) {
    if (cause.status === -1) return
    error.value = cause.message
    if (cause.status === 0) error.value += ' 请刷新页面核对已保存的主题。'
    if (cause.status === 401) emit('session-expired')
  } finally {
    saving.value = false
    emit('busy-change', false)
  }
}

function clearAvatarSelection() {
  if (avatarPreview.value) URL.revokeObjectURL(avatarPreview.value)
  avatarPreview.value = ''
  avatarFile.value = null
}

function chooseAvatar(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file || saving.value || props.disabled) return
  notice.value = ''
  error.value = ''
  clearAvatarSelection()
  if (!/\.(png|jpe?g)$/i.test(file.name) || !file.size || file.size > 2 * 1024 * 1024) {
    error.value = '请选择不超过 2MB 的 PNG/JPG/JPEG 图片。'
    return
  }
  avatarFile.value = file
  avatarPreview.value = URL.createObjectURL(file)
}

async function changeAvatar(method) {
  if (saving.value || props.disabled || (method === 'POST' && !avatarFile.value)) return
  if (method === 'DELETE' && !window.confirm('恢复默认头像会移除当前自定义头像，确定继续？')) return
  saving.value = true
  emit('busy-change', true)
  notice.value = ''
  error.value = ''
  try {
    let body
    if (method === 'POST') {
      body = new FormData()
      body.append('file', avatarFile.value)
    }
    const data = await requestApi('/api/auth/me/avatar', {
      method, body, csrfToken: props.csrfToken, signal: lifetime.signal, timeoutMs: 30000,
    })
    emit('saved', data.user)
    clearAvatarSelection()
    notice.value = method === 'POST' ? '头像已保存。' : '已恢复默认头像。'
  } catch (cause) {
    if (cause.status === -1) return
    error.value = cause.message
    if (cause.status === 0) error.value += ' 请先刷新页面核对头像，再决定是否重试。'
    if (cause.status === 401) emit('session-expired')
  } finally {
    saving.value = false
    emit('busy-change', false)
  }
}

async function save() {
  if (saving.value || props.disabled || !dirty.value) return
  saving.value = true
  emit('busy-change', true)
  notice.value = ''
  error.value = ''
  try {
    const data = await requestApi('/api/auth/me', {
      method: 'PATCH', body: { nickname: nickname.value.trim() },
      csrfToken: props.csrfToken, signal: lifetime.signal,
    })
    nickname.value = data.user.nickname
    emit('saved', data.user)
    notice.value = data.user.nickname ? '昵称已保存。' : '已恢复显示登录用户名。'
  } catch (cause) {
    if (cause.status === -1) return
    error.value = cause.message
    if (cause.status === 0) error.value += ' 请先刷新页面核对昵称，再决定是否重新保存。'
    if (cause.status === 401) emit('session-expired')
  } finally {
    saving.value = false
    emit('busy-change', false)
  }
}
onBeforeUnmount(() => { lifetime.abort(); clearAvatarSelection() })
</script>

<template>
  <details class="profile-settings" :aria-busy="saving">
    <summary>个人设置</summary>
    <form @submit.prevent="save">
      <label :for="inputId">昵称<input :id="inputId" v-model="nickname" maxlength="30" autocomplete="nickname" :disabled="saving || disabled" placeholder="最多 30 个字符，留空恢复用户名" /></label>
      <ElButton type="primary" native-type="submit" :loading="saving" :disabled="disabled || saving || !dirty">保存昵称</ElButton>
    </form>
    <p>昵称用于个人空间展示，可与他人相同；登录仍使用用户名「{{ user.username }}」。</p>
    <div class="avatar-settings">
      <label :for="avatarInputId">头像图片<input :id="avatarInputId" type="file" accept=".png,.jpg,.jpeg" :disabled="saving || disabled" @change="chooseAvatar" /></label>
      <p>支持 PNG、JPG、JPEG，最多 2MB；保存时居中裁成 256 × 256 正方形。选择后点击保存才会更新。</p>
      <img v-if="avatarPreview" :src="avatarPreview" class="avatar-preview" alt="待保存头像预览" />
      <div class="avatar-actions">
        <ElButton type="primary" :disabled="saving || disabled || !avatarFile" @click="changeAvatar('POST')">保存头像</ElButton>
        <ElButton v-if="avatarFile" :disabled="saving || disabled" @click="clearAvatarSelection">取消选择</ElButton>
        <ElButton v-if="user.avatar_url" :disabled="saving || disabled" @click="changeAvatar('DELETE')">恢复默认头像</ElButton>
      </div>
    </div>
    <form @submit.prevent="saveTheme">
      <label :for="themeInputId">主题<select :id="themeInputId" v-model="theme" :disabled="saving || disabled"><option value="default">默认（原有绿色）</option><option value="light">浅色</option><option value="dark">深色</option></select></label>
      <ElButton type="primary" native-type="submit" :disabled="saving || disabled || theme === (user.theme || 'default')">保存主题</ElButton>
    </form>
    <p>保存后整页应用，刷新或重新登录仍保留；退出登录恢复默认主题。</p>
    <form @submit.prevent="saveFont">
      <label :for="fontInputId">字体<select :id="fontInputId" v-model="font" :disabled="saving || disabled"><option value="default">默认（微软雅黑优先）</option><option value="song">宋体</option><option value="kai">楷体</option></select></label>
      <ElButton type="primary" native-type="submit" :disabled="saving || disabled || font === (user.font || 'default')">保存字体</ElButton>
    </form>
    <p :style="{ fontFamily: previewFont }">字体预览：数学让思考更清晰。MathRAG 123</p>
    <p>保存后应用到页面文字，刷新或重新登录仍保留。使用电脑已安装字体；数学公式和代码保留专用字体。</p>
    <p v-if="notice" class="profile-notice" role="status">{{ notice }}</p>
    <p v-if="error" class="profile-error" role="alert">{{ error }}</p>
  </details>
</template>

<style scoped>
.profile-settings{margin:20px 0;padding:16px;border:1px solid var(--app-border, #dce3d6);border-radius:8px}.profile-settings summary{cursor:pointer;color:var(--app-text, #365b44);font-size:14px}.profile-settings form{display:flex;align-items:end;gap:14px;margin-top:16px;flex-wrap:wrap}.profile-settings label{display:flex;flex-direction:column;gap:8px;font-size:12px;color:var(--app-text, #566b54)}.profile-settings input{width:320px;max-width:100%;height:36px;border:1px solid var(--app-border, #dce3d6);border-radius:6px;padding:0 10px;font:inherit;color:var(--app-text, #263f31)}.profile-settings input:focus{outline:2px solid var(--app-border, #93bda5)}.profile-settings p{font-size:12px;line-height:1.8;color:var(--app-muted, #7d8c74)}.profile-settings .profile-notice{color:var(--app-text, #367449)}.profile-settings .profile-error{color:var(--app-danger, #a64536)}
.avatar-settings{border-top:1px solid var(--app-border, #e4e9df);margin-top:18px;padding-top:18px}.avatar-settings input[type=file]{width:auto;height:auto;border:0;padding:8px 0}.avatar-preview{display:block;width:80px;height:80px;object-fit:cover;border-radius:12px;margin:12px 0}.avatar-actions{display:flex;gap:10px}.avatar-actions .el-button+.el-button{margin-left:0}
</style>
