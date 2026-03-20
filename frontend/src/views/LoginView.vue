<template>
  <div class="h-[100dvh] bg-[#1d1d22] relative flex flex-col overflow-hidden">
    <AppHeader title="密码登录" />

    <!-- 主体内容（可滚动，键盘弹起时内容不被遮挡） -->
    <main class="relative z-10 flex flex-col flex-1 overflow-y-auto px-6 pt-10 pb-10 max-w-md mx-auto w-full">
      <form class="flex flex-col gap-6" @submit.prevent="handleLogin">
        <!-- 邮箱输入框 -->
        <div class="relative">
          <input
            v-model="email"
            type="email"
            placeholder="输入邮箱"
            autocomplete="email"
            class="w-full h-14 rounded-full bg-[rgba(153,155,255,0.05)] border border-dashed border-[#999bff] px-6 text-base text-white placeholder:text-white/30 outline-none focus:border-[#999bff] focus:bg-[rgba(153,155,255,0.08)] transition-colors"
          />
        </div>

        <!-- 密码输入框 -->
        <div class="relative">
          <input
            v-model="password"
            :type="showPassword ? 'text' : 'password'"
            placeholder="输入密码"
            autocomplete="current-password"
            class="w-full h-14 rounded-full bg-[rgba(153,155,255,0.05)] border border-dashed border-[#999bff] px-6 pr-14 text-base text-white placeholder:text-white/30 outline-none focus:border-[#999bff] focus:bg-[rgba(153,155,255,0.08)] transition-colors"
          />
          <button
            type="button"
            class="absolute right-5 top-1/2 -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
            @click="showPassword = !showPassword"
            :aria-label="showPassword ? '隐藏密码' : '显示密码'"
          >
            <svg v-if="!showPassword" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
            </svg>
            <svg v-else width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" /><path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" /><line x1="1" y1="1" x2="23" y2="23" />
            </svg>
          </button>
        </div>

        <!-- 辅助链接行 -->
        <div class="flex items-center justify-between px-1 text-sm">
          <button type="button" class="text-[#999bff] hover:text-[#b8b9ff] transition-colors" @click="switchToCode">
            用验证码登录
          </button>
          <button type="button" class="text-white/50 hover:text-white/70 transition-colors" @click="forgotPassword">
            忘记密码？
          </button>
        </div>

        <!-- 登录按钮 -->
        <button
          type="submit"
          :disabled="isLoading"
          class="relative w-full h-14 rounded-full overflow-hidden shadow-[0px_4px_0px_0px_rgba(0,0,0,0.2)] transition-opacity hover:opacity-90 active:opacity-80 disabled:opacity-50 disabled:cursor-not-allowed mt-2"
        >
          <!-- 按钮背景 -->
          <div class="absolute inset-0 bg-[#5c5fff] rounded-full" />
          <!-- 内边框装饰 -->
          <div class="absolute inset-[5px_2px] border border-dashed border-[#cfd0dd]/60 rounded-full pointer-events-none" />
          <!-- 左右小星星装饰 -->
          <img :src="star" alt="" class="absolute left-2 top-1/2 -translate-y-1/2 w-2 h-2 pointer-events-none" />
          <img :src="star" alt="" class="absolute right-2 top-1/2 -translate-y-1/2 w-2 h-2 pointer-events-none" />
          <!-- 按钮文字 -->
          <span
            v-if="!isLoading"
            class="relative font-bold text-lg tracking-widest text-white"
            style="text-shadow: 0px 2px 0px rgba(0,0,0,0.27);"
          >验证</span>
          <!-- 加载中 -->
          <span v-else class="relative flex items-center justify-center gap-1.5">
            <span class="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-1.5 h-1.5 bg-white rounded-full animate-bounce" style="animation-delay: 300ms" />
          </span>
        </button>

        <!-- 错误提示 -->
        <p v-if="errorMsg" class="text-red-400/80 text-sm text-center -mt-2">{{ errorMsg }}</p>
      </form>
    </main>

    <!-- 底部 -->
    <footer class="relative z-10 flex justify-center pb-8">
      <p class="text-sm text-white/50">
        All right reserved
      </p>
    </footer>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import AppHeader from '../components/AppHeader.vue'
import btnLightLeft from '../assets/login/btn-light-left.svg'
import btnLightRight from '../assets/login/btn-light-right.svg'
import btnMask from '../assets/login/btn-mask.png'
import star from '../assets/login/star.svg'

const router = useRouter()

const email = ref('')
const password = ref('')
const showPassword = ref(false)
const isLoading = ref(false)
const errorMsg = ref('')

async function handleLogin() {
  errorMsg.value = ''
  // if (!email.value || !password.value) {
  //   errorMsg.value = '请填写邮箱和密码'
  //   return
  // }
  isLoading.value = true
  try {
    // TODO: 接入实际登录接口
    // await new Promise(resolve => setTimeout(resolve, 1000))
    router.push('/conversation')
  } catch (e) {
    errorMsg.value = e?.message || '登录失败，请重试'
  } finally {
    isLoading.value = false
  }
}

function switchToCode() {
  // TODO: 跳转到验证码登录页
}

function forgotPassword() {
  // TODO: 跳转到忘记密码页
}

function goRegister() {
  // TODO: 跳转到注册页
}
</script>
