import { createRouter, createWebHistory } from 'vue-router'
import ChatView from '../views/ChatView.vue'
import LoginView from '../views/LoginView.vue'
import ConversationListView from '../views/ConversationListView.vue'

const routes = [
  { path: '/', redirect: '/login' },
  { path: '/login', component: LoginView },
  { path: '/conversation', component: ConversationListView },
  { path: '/chat', component: ChatView },
]

export default createRouter({
  history: createWebHistory(),
  routes,
})
