import { createRouter, createWebHistory } from 'vue-router'
import AdminView from '../views/AdminView.vue'

const routes = [
  { path: '/', redirect: '/admin' },
  { path: '/admin', component: AdminView },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
