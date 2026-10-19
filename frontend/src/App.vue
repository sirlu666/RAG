<script setup lang="ts">
import { RouterView } from 'vue-router'
</script>

<template>
  <div class="app-shell">
    <header class="app-header">
      <div class="brand">
        <span class="logo">∑</span>
        <span>MathRAG</span>
        <span class="tag">数学智能答疑</span>
      </div>
      <nav class="actions">
        <!-- P1: 知识库 / 历史 / 设置 / 登录态 -->
        <el-button text>知识库</el-button>
        <el-button text>历史</el-button>
        <el-button type="primary" round>登录</el-button>
      </nav>
    </header>
    <main class="app-main">
      <RouterView />
    </main>
  </div>
</template>

<style>
* { box-sizing: border-box; }
html, body, #app { height: 100%; margin: 0; }
body {
  font-family: 'Inter', 'PingFang SC', 'Microsoft YaHei', system-ui, sans-serif;
  background: #f7f8fa;
  color: #1f2329;
}
.app-shell { display: flex; flex-direction: column; height: 100%; }
.app-header {
  height: 56px; flex: none; display: flex; align-items: center; justify-content: space-between;
  padding: 0 20px; background: #fff; border-bottom: 1px solid #ebeef5;
}
.brand { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.logo {
  width: 26px; height: 26px; display: grid; place-items: center;
  border-radius: 8px; background: linear-gradient(135deg, #4b6cf5, #7b5cf5);
  color: #fff; font-size: 15px;
}
.tag { font-weight: 400; font-size: 12px; color: #909399; }
.app-main { flex: 1; min-height: 0; }
</style>
