<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElButton, ElTag } from 'element-plus'
import { requestApi } from '../api.js'
import KnowledgeBasePanel from './KnowledgeBasePanel.vue'
import PublicKnowledgePanel from './PublicKnowledgePanel.vue'
import ProfilePanel from './ProfilePanel.vue'

const props = defineProps({ view: { type: String, default: 'home' } })
const emit = defineEmits(['navigate'])
const mode = ref('login')
const user = ref(null)
const publicRevision = ref(0)
const csrfToken = ref('')
const restoring = ref(true)
const busy = ref(false)
const profileBusy = ref(false)
const error = ref('')
const notice = ref('')
const form = reactive({ username: '', password: '', confirm: '' })
const registering = computed(() => mode.value === 'register')
const displayName = computed(() => user.value?.nickname || user.value?.username || '')
const avatarLetter = computed(() => Array.from(displayName.value)[0]?.toUpperCase() || '')
watch(() => user.value?.font, font => {
  document.documentElement.dataset.font = ['song', 'kai'].includes(font) ? font : 'default'
}, { immediate: true })
watch(() => user.value?.theme, theme => {
  document.documentElement.dataset.theme = ['light', 'dark'].includes(theme) ? theme : 'default'
  document.documentElement.classList.toggle('dark', theme === 'dark')
}, { immediate: true })

function applySession(data) {
  user.value = data.user
  csrfToken.value = data.csrf_token
}

function expireSession() {
  user.value = null
  csrfToken.value = ''
  notice.value = ''
  error.value = '登录已过期，请重新登录。'
  emit('navigate', 'account')
}

async function restoreSession() {
  restoring.value = true
  error.value = ''
  notice.value = ''
  try {
    applySession(await requestApi('/api/auth/me'))
  } catch (cause) {
    if (cause.status === 401) {
      user.value = null
      csrfToken.value = ''
    } else {
      error.value = cause.message
    }
  } finally {
    restoring.value = false
  }
}

function changeMode(value) {
  mode.value = value
  form.password = ''
  form.confirm = ''
  error.value = ''
  notice.value = ''
}

async function submit() {
  error.value = ''
  notice.value = ''
  if (registering.value && form.password !== form.confirm) {
    error.value = '两次输入的密码不一致。'
    return
  }
  if (busy.value || restoring.value) return
  busy.value = true
  try {
    const data = await requestApi(`/api/auth/${mode.value}`, {
      method: 'POST', body: { username: form.username.trim(), password: form.password },
    })
    applySession(data)
    form.password = ''
    form.confirm = ''
    notice.value = registering.value ? '账号已创建，已为你登录。' : '登录成功。'
    emit('navigate', 'home')
  } catch (cause) {
    error.value = cause.message
    form.password = ''
    form.confirm = ''
  } finally {
    busy.value = false
  }
}

async function logout() {
  if (busy.value || profileBusy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await requestApi('/api/auth/logout', { method: 'POST', csrfToken: csrfToken.value })
    user.value = null
    csrfToken.value = ''
    notice.value = '已退出登录。'
    emit('navigate', 'home')
  } catch (cause) {
    if (cause.status === 401) {
      user.value = null
      csrfToken.value = ''
      notice.value = '登录已过期，请重新登录。'
    } else {
      error.value = `${cause.message} 尚未确认退出，请重试。`
    }
  } finally {
    busy.value = false
  }
}

async function checkPrivateAccess() {
  if (busy.value || profileBusy.value) return
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const documents = await requestApi('/api/docs')
    notice.value = `个人文档接口访问成功，当前账号有 ${documents.length} 份文档。`
  } catch (cause) {
    error.value = cause.message
    if (cause.status === 401) {
      user.value = null
      csrfToken.value = ''
    }
  } finally {
    busy.value = false
  }
}

onMounted(restoreSession)
</script>

<template>
  <div class="account-workspace">
  <section v-show="props.view === 'account'" class="panel account-panel" aria-labelledby="account-title" :aria-busy="busy || restoring">
    <div class="panel-heading"><div><span class="eyebrow">02 / YOUR SPACE</span><h2 id="account-title">账号与个人空间</h2></div><ElTag :type="user ? 'success' : 'info'" effect="plain">{{ user ? '已登录' : '未登录' }}</ElTag></div>
    <p v-if="restoring" class="account-hint" role="status">正在恢复登录状态…</p>
    <template v-else-if="user">
      <div class="account-user"><div class="account-avatar"><img v-if="user.avatar_url" :src="user.avatar_url" alt="个人头像" /><span v-else aria-hidden="true">{{ avatarLetter }}</span></div><div><strong>{{ displayName }}</strong><p>登录用户名：{{ user.username }} · 欢迎回来，你的个人空间已就绪。</p></div></div>
      <div class="account-actions"><ElButton :disabled="busy || profileBusy" @click="checkPrivateAccess">检查我的文档权限</ElButton><ElButton :loading="busy" :disabled="profileBusy" @click="logout">退出登录</ElButton></div>
      <ProfilePanel :key="user.id" :user="user" :csrf-token="csrfToken" :disabled="busy" @saved="user = $event" @busy-change="profileBusy = $event" @session-expired="expireSession" />
      <p class="account-hint">刷新页面后将自动恢复登录；个人知识库按账号独立保存。</p>
    </template>
    <template v-else>
      <div class="account-tabs" aria-label="账号操作"><button type="button" :class="{ selected: !registering }" :aria-pressed="!registering" :disabled="busy" @click="changeMode('login')">登录</button><button type="button" :class="{ selected: registering }" :aria-pressed="registering" :disabled="busy" @click="changeMode('register')">创建账号</button></div>
      <form class="account-form" @submit.prevent="submit">
        <label for="account-username">用户名<input id="account-username" v-model="form.username" name="username" autocomplete="username" minlength="3" maxlength="32" required :disabled="busy" placeholder="3–32 位中文、字母、数字或下划线" /></label>
        <label for="account-password">密码<input id="account-password" v-model="form.password" name="password" type="password" :autocomplete="registering ? 'new-password' : 'current-password'" minlength="8" maxlength="128" required :disabled="busy" placeholder="8–128 位，区分大小写" /></label>
        <label v-if="registering" for="account-confirm">确认密码<input id="account-confirm" v-model="form.confirm" name="confirm" type="password" autocomplete="new-password" minlength="8" maxlength="128" required :disabled="busy" placeholder="再次输入密码" /></label>
        <ElButton type="primary" native-type="submit" :loading="busy">{{ registering ? '创建账号并登录' : '登录' }}</ElButton>
      </form>
      <p class="account-hint">用户名不区分英文字母大小写。退出后，个人资料接口将拒绝访问。</p>
    </template>
    <p v-if="notice" class="account-notice" role="status">{{ notice }}</p>
    <div v-if="error" class="account-error" role="alert"><p>{{ error }}</p><ElButton v-if="!busy && !restoring" size="small" @click="restoreSession">重新连接</ElButton></div>
  </section>
  <div v-show="props.view === 'home'" class="panel study-panel">
    <p v-if="restoring" class="account-hint" role="status">正在读取你的知识空间…</p>
    <KnowledgeBasePanel v-if="user && !restoring" :key="user.id" :csrf-token="csrfToken" @session-expired="expireSession" @publication-changed="publicRevision++" />
    <div v-else-if="!restoring" class="login-prompt"><div><h2>个人知识库</h2><p>登录后管理自己的资料、保存对话并查看引用。</p></div><ElButton type="primary" @click="emit('navigate', 'account')">登录 / 注册</ElButton></div>
    <PublicKnowledgePanel v-if="!restoring" :key="user?.id || 'guest'" :authenticated="!!user" :csrf-token="csrfToken" :revision="publicRevision" @session-expired="expireSession" />
  </div>
  </div>
</template>

<style scoped>
.account-panel{margin-top:0}.login-prompt{display:flex;align-items:center;justify-content:space-between;gap:20px}.login-prompt h2{margin:0}.login-prompt p{font-size:13px;color:var(--app-muted,#7d8c74)}

.account-tabs{display:flex;gap:8px;margin-top:24px}.account-tabs button{background:var(--app-soft, #f3f5ee);border:1px solid var(--app-border, #dfe6d9);border-radius:8px;padding:9px 20px;color:var(--app-muted, #687964);cursor:pointer}.account-tabs button.selected{background:var(--app-soft, #e7f0e4);border-color:var(--app-accent, #8eaf87);color:var(--app-text, #21543b)}.account-tabs button:disabled{cursor:wait;opacity:.6}.account-form{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:18px;margin-top:20px;align-items:end}.account-form label{display:flex;flex-direction:column;gap:9px;font-size:12px;color:var(--app-text, #566b54)}.account-form input{width:100%;height:41px;border:1px solid var(--app-border, #dce3d6);border-radius:8px;background:var(--app-surface, #fdfefb);padding:0 12px;font:inherit;color:var(--app-text, #263f31)}.account-form input:focus{outline:2px solid var(--app-border, #93bda5);outline-offset:2px}.account-form .el-button{justify-self:start;min-width:130px;height:41px}.account-hint{font-size:12px;color:var(--app-muted, #7d8c74);line-height:1.9;margin:19px 0 0}.account-user{display:flex;gap:14px;align-items:center;margin:24px 0}.account-avatar{width:45px;height:45px;border-radius:12px;background:var(--app-soft, #e7efdf);color:var(--app-text, #48714d);display:grid;place-items:center;font-size:22px}.account-avatar{overflow:hidden;flex-shrink:0}.account-avatar img{display:block;width:100%;height:100%;object-fit:cover}.account-user strong{font-size:17px}.account-user p{font-size:12px;color:var(--app-muted, #7d8c74);margin:7px 0 0}.account-actions{display:flex;gap:10px;flex-wrap:wrap}.account-actions .el-button+.el-button{margin-left:0}.account-notice{font-size:13px;color:var(--app-text, #367449);background:var(--app-soft, #edf5e8);padding:13px;border-radius:8px;line-height:1.8}.account-error{color:var(--app-danger, #a64536);font-size:13px;background:var(--app-danger-bg, #fbefea);padding:12px 16px;border-radius:8px;line-height:1.8;margin-top:16px}.account-error p{margin:0 0 8px}@media(max-width:650px){.account-form{grid-template-columns:1fr}.account-form .el-button{width:100%}}
</style>
