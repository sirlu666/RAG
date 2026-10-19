import { createRouter, createWebHistory } from 'vue-router'

export default createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'chat', component: () => import('@/views/ChatView.vue') },
    // P1 逐个补：/login /kbs /docs /setting
  ],
})
