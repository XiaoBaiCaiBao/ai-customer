<template>
  <div class="h-[100dvh] bg-[#1d1d22] relative flex flex-col overflow-hidden">
    <AppHeader title="进入对话" />

    <main class="relative z-10 flex flex-col flex-1 overflow-y-auto px-6 pt-10 pb-10 max-w-md mx-auto w-full">
      <form class="flex flex-col gap-6" @submit.prevent="handleLogin">
        <div class="relative">
          <input
            v-model="nickname"
            type="text"
            inputmode="text"
            placeholder="请输入用户名"
            autocomplete="username"
            class="w-full h-14 rounded-full bg-[rgba(153,155,255,0.05)] border border-dashed border-[#999bff] px-6 text-base text-white placeholder:text-white/30 outline-none focus:border-[#999bff] focus:bg-[rgba(153,155,255,0.08)] transition-colors"
          />
        </div>

        <button
          type="submit"
          :disabled="isLoading"
          class="relative w-full h-14 rounded-full overflow-hidden shadow-[0px_4px_0px_0px_rgba(0,0,0,0.2)] transition-opacity hover:opacity-90 active:opacity-80 disabled:opacity-50 disabled:cursor-not-allowed mt-2"
        >
          <div class="absolute inset-0 bg-[#5c5fff] rounded-full" />
          <div class="absolute inset-[5px_2px] border border-dashed border-[#cfd0dd]/60 rounded-full pointer-events-none" />
          <img :src="star" alt="" class="absolute left-2 top-1/2 -translate-y-1/2 w-2 h-2 pointer-events-none" />
          <img :src="star" alt="" class="absolute right-2 top-1/2 -translate-y-1/2 w-2 h-2 pointer-events-none" />
          <span
            v-if="!isLoading"
            class="relative font-bold text-lg tracking-widest text-white"
            style="text-shadow: 0px 2px 0px rgba(0,0,0,0.27);"
          >进入</span>
          <span v-else class="relative flex items-center justify-center gap-1.5">
            <span class="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style="animation-delay: 300ms" />
          </span>
        </button>

        <p v-if="errorMsg" class="text-red-400/80 text-sm text-center -mt-2">{{ errorMsg }}</p>
      </form>
    </main>

    <footer class="relative z-10 flex justify-center pb-8">
      <p class="text-sm text-white/50">All right reserved</p>
    </footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import AppHeader from '../components/AppHeader.vue'
import star from '../assets/login/star.svg'
import { ALLOWED_USER_ID } from '../utils/auth'

const router = useRouter()
const chatStore = useChatStore()
const nickname = ref('')
const isLoading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  errorMsg.value = ''
  const name = nickname.value.trim()
  if (!name) {
    errorMsg.value = '请先输入内容'
    return
  }
  if (name !== ALLOWED_USER_ID) {
    errorMsg.value = '用户名不正确'
    return
  }
  isLoading.value = true
  try {
    const res = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nickname: name })
    })
    const data = await res.json()
    if (!res.ok) {
      const detail = data.detail
      throw new Error(typeof detail === 'string' ? detail : (Array.isArray(detail) ? detail[0]?.msg : '进入失败，请重试'))
    }
    localStorage.setItem('chat_token', data.access_token)
    localStorage.setItem('chat_user_id', data.user_id)
    chatStore.refreshUser()
    router.push('/chat')
  } catch (e) {
    errorMsg.value = e?.message || '进入失败，请重试'
  } finally {
    isLoading.value = false
  }
}
</script>
