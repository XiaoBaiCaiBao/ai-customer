import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import LoginView from '../views/LoginView.vue'
import ConversationListView from '../views/ConversationListView.vue'
import { hasValidLocalAuth, clearLocalAuth } from '../utils/auth'

const routes = [
  { path: '/', component: LoginView },
  { path: '/login', redirect: '/' },
  { path: '/conversation', component: ConversationListView, meta: { requiresAuth: true } },
  { path: '/chat', component: ChatView, meta: { requiresAuth: true } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  const isAuthed = hasValidLocalAuth()
  if (!isAuthed) {
    clearLocalAuth()
  }

  if (to.meta.requiresAuth && !isAuthed) {
    next('/')
    return
  }
  if ((to.path === '/' || to.path === '/login') && isAuthed) {
    next('/chat')
    return
  }
  next()
})

export default router
