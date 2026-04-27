<template>
  <div class="flex flex-col h-[100%] text-white relative" :class="isRafayel ? 'bg-[#0e0e14]' : 'bg-[#1d1d22]'">

    <!-- 背景：Rafayel 显示背景图，AI助手 纯色 -->
    <div class="absolute inset-0 pointer-events-none z-0">
      <template v-if="isRafayel">
        <div class="overflow-hidden">
          <img :src="bgImage" alt="" class="w-full object-contain object-top" />
        </div>
      </template>
    </div>

    <!-- Header -->
    <AppHeader title="你的小客服" :show-back="true">
      <template #right>
        <div class="flex items-center gap-2">
          <button
            @click="chatStore.toggleDeveloperMode()"
            class="text-xs px-2 py-1 border rounded-lg transition-colors whitespace-nowrap"
            :class="chatStore.developerMode
              ? 'border-emerald-400 text-emerald-300 bg-emerald-500/10'
              : 'border-gray-500 text-gray-400 hover:text-white'"
          >
            调试
          </button>
          <button
            @click="logout"
            class="text-xs px-2 py-1 border border-gray-500 rounded-lg text-gray-400 hover:text-white transition-colors whitespace-nowrap"
          >
            退出
          </button>
        </div>
      </template>
    </AppHeader>

    <!-- 消息列表 -->
    <div
      ref="scrollRef"
      class="flex-1 overflow-y-auto px-4 py-4 space-y-1 relative z-10"
    >
      <div class="flex justify-center py-4">
        <div
          class="px-4 py-2 rounded-2xl border border-surface-border bg-surface-card text-sm text-white/55 shadow-[0_8px_24px_rgba(0,0,0,0.16)] backdrop-blur-sm"
        >
          Hi，很高兴为你服务~
        </div>
      </div>

      <!-- 对话消息 -->
      <MessageBubble
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :message="msg"
        :developer-mode="chatStore.developerMode"
      />

      <!-- 思考中动画（无消息时显示，有消息后由 MessageBubble 内部处理） -->
      <div v-if="chatStore.isThinking && !hasStreamingMessage" class="flex flex-col gap-1 mb-4">
        <span class="text-xs font-semibold tracking-widest text-gray-500 uppercase px-1">
          AI助手
        </span>
        <div class="flex items-center gap-1.5 px-4 py-3 bg-surface-card border border-surface-border rounded-2xl rounded-tl-sm w-fit">
          <span class="text-sm animate-spin" style="display:inline-block">🧠</span>
          <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:0ms" />
          <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:150ms" />
          <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:300ms" />
          <span class="text-xs text-gray-500 ml-1">
            {{ intentThinkingLabel }}
          </span>
        </div>
      </div>
    </div>

    <!-- 快捷操作 chips -->
    <div class="px-4 pt-2 flex gap-2 overflow-x-auto flex-shrink-0 relative z-10 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
      <button
        v-for="chip in quickChips"
        :key="chip"
        @click="handleChip(chip)"
        class="flex-shrink-0 text-xs px-3 py-1.5 rounded-full border border-surface-border bg-surface-card text-gray-300 hover:border-accent hover:text-white transition-colors whitespace-nowrap"
      >
        {{ chip }}
      </button>
    </div>

    <!-- 图片预览区 -->
    <div v-if="pendingImages.length" class="px-4 pb-2 flex gap-2 flex-wrap flex-shrink-0 relative z-10">
      <div
        v-for="(img, i) in pendingImages"
        :key="i"
        class="relative w-16 h-16 rounded-xl overflow-hidden border border-surface-border group"
      >
        <img :src="img.url" class="w-full h-full object-cover" />
        <button
          @click="removeImage(i)"
          class="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center text-white"
        >
          <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- 输入栏 -->
    <div class="px-4 pt-2 pb-3 flex-shrink-0 relative z-10">
      <div class="flex items-center gap-3 bg-surface-card border border-surface-border rounded-2xl px-4 py-2.5">
        <!-- 左侧加号：切换 more panel -->
        <button
          @click="togglePanel"
          class="flex-shrink-0 transition-colors text-gray-500"
        >
          <svg class="w-5 h-5 transition-transform duration-200" :class="showPanel ? 'rotate-45' : ''" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
        </button>

        <input
          v-model="inputText"
          @keydown.enter.prevent="handleSend"
          type="text"
          placeholder="输入你想说的话..."
          class="flex-1 bg-transparent text-sm text-gray-200 placeholder-gray-600 outline-none"
          :disabled="chatStore.isThinking"
        />

        <button
          @click="handleSend"
          :disabled="(!inputText.trim() && !pendingImages.length) || chatStore.isThinking"
          class="flex-shrink-0 w-8 h-8 rounded-full bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
        >
          <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
      <p v-if="panelNotice" class="text-xs text-white/60 pt-2 px-1">{{ panelNotice }}</p>
    </div>

    <!-- 更多 Panel（从底部滑入） -->
    <transition
      enter-active-class="overflow-hidden transition-[max-height,opacity,transform] duration-300 ease-linear"
      enter-from-class="max-h-0 translate-y-4 opacity-0"
      enter-to-class="max-h-64 translate-y-0 opacity-100"
      leave-active-class="overflow-hidden transition-[max-height,opacity,transform] duration-300 ease-linear"
      leave-from-class="max-h-64 translate-y-0 opacity-100"
      leave-to-class="max-h-0 translate-y-4 opacity-0"
    >
      <div
        v-if="showPanel"
        class="flex-shrink-0 border-surface-border px-6 pt-1 relative z-10 will-change-[max-height,transform,opacity]"
      >
        <div class="flex gap-6 flex-wrap pb-6">
          <!-- 图片上传 -->
          <button
            @click="triggerImageUpload"
            class="flex flex-col items-center gap-2 group"
          >
            <div class="w-14 h-14 rounded-2xl bg-surface-card border border-surface-border flex items-center justify-center group-hover:border-accent group-active:scale-95 transition-all">
              <svg class="w-6 h-6 text-gray-300 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <rect x="3" y="3" width="18" height="18" rx="3" stroke-width="1.5"/>
                <circle cx="8.5" cy="8.5" r="1.5" stroke-width="1.5"/>
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 15l-5-5L5 21"/>
              </svg>
            </div>
            <span class="text-xs text-gray-400 group-hover:text-white transition-colors">图片</span>
          </button>

          <button
            @click="restartSession"
            :disabled="sessionActionLoading"
            class="flex flex-col items-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div class="w-14 h-14 rounded-2xl bg-surface-card border border-surface-border flex items-center justify-center group-hover:border-accent transition-all">
              <svg class="w-6 h-6 text-gray-300 group-hover:text-white transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
            </div>
            <span class="text-xs text-gray-400 group-hover:text-white transition-colors">重启会话</span>
          </button>

          <button
            @click="resetChat"
            :disabled="sessionActionLoading"
            class="flex flex-col items-center gap-2 group disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <div class="w-14 h-14 rounded-2xl bg-surface-card border border-surface-border flex items-center justify-center group-hover:border-red-400 transition-all">
              <svg class="w-6 h-6 text-gray-300 group-hover:text-red-300 transition-colors" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10 11v6m4-6v6m-7 4h10a2 2 0 002-2V7H5v12a2 2 0 002 2Zm9-14h-3.5l-1-1h-3l-1 1H4"/>
              </svg>
            </div>
            <span class="text-xs text-gray-400 group-hover:text-red-300 transition-colors">重置聊天</span>
          </button>
        </div>
      </div>
    </transition>

    <!-- 隐藏的文件 input -->
    <input
      ref="fileInputRef"
      type="file"
      accept="image/*"
      multiple
      class="hidden"
      @change="handleImageSelect"
    />

  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useChatStore } from '../stores/chat'
import AppHeader from '../components/AppHeader.vue'
import MessageBubble from '../components/MessageBubble.vue'
import bgImage from '../assets/common/Rafayel.webp'
import { clearLocalAuth } from '../utils/auth'

const route = useRoute()
const router = useRouter()
const isRafayel = computed(() => route.query.agent === 'rafayel')

const chatStore = useChatStore()
const inputText = ref('')
const scrollRef = ref(null)
const showPanel = ref(false)
const fileInputRef = ref(null)
const pendingImages = ref([]) // [{ url: string, dataUrl: string, name: string }]
const sessionActionLoading = ref(false)
const panelNotice = ref('')

function logout() {
  clearLocalAuth()
  chatStore.resetSessionState()
  chatStore.refreshUser()
  router.push('/')
}

async function restartSession() {
  if (sessionActionLoading.value) return
  if (!confirm('确定要重启当前会话吗？这会删除当前会话的短期记忆和聊天上下文。')) return

  sessionActionLoading.value = true
  panelNotice.value = '正在重启会话...'
  try {
    await chatStore.clearHistory()
    pendingImages.value = []
    inputText.value = ''
    showPanel.value = false
    panelNotice.value = '当前会话已重启，长期记忆保持不变。'
  } catch {
    panelNotice.value = '重启会话失败，请稍后重试。'
  } finally {
    sessionActionLoading.value = false
  }
}

async function resetChat() {
  if (sessionActionLoading.value) return
  if (!confirm('确定要重置聊天吗？这会删除所有历史聊天记录以及当前保存的长短期记忆。')) return

  sessionActionLoading.value = true
  panelNotice.value = '正在重置聊天...'
  try {
    await chatStore.resetChat()
    pendingImages.value = []
    inputText.value = ''
    showPanel.value = false
    panelNotice.value = '聊天已重置。'
  } catch {
    panelNotice.value = '重置聊天失败，请稍后重试。'
  } finally {
    sessionActionLoading.value = false
  }
}

const quickChips = [
  '聊天时为什么出现红色感叹号',
  '帮我查询北京天气',
  '我充了月卡但体力没到账',
  '会员权益',
  '积分问题',
]

const hasStreamingMessage = computed(() =>
  chatStore.messages.some(m => m.streaming)
)

const INTENT_THINKING_LABELS = {
  product_info: '查询知识库中…',
  usage_issue:  '检索问题解决方案…',
  complaint:    '记录用户反馈…',
  aftersales:   '核查订单与资产…',
  event:        '查询活动信息…',
  web_search:   '联网查询中…',
  chat:         '思考回复中…',
}

const intentThinkingLabel = computed(() => {
  const intent = chatStore.currentIntent
  return INTENT_THINKING_LABELS[intent] || '思考中…'
})

function togglePanel() {
  showPanel.value = !showPanel.value
}

function triggerImageUpload() {
  fileInputRef.value?.click()
}

async function readFileAsDataUrl(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result)
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

async function compressImageFile(file) {
  const originalDataUrl = await readFileAsDataUrl(file)

  if (file.type === 'image/gif') {
    return originalDataUrl
  }

  const img = await new Promise((resolve, reject) => {
    const el = new Image()
    el.onload = () => resolve(el)
    el.onerror = reject
    el.src = originalDataUrl
  })

  const maxSide = 1600
  const scale = Math.min(1, maxSide / Math.max(img.width, img.height))
  const width = Math.max(1, Math.round(img.width * scale))
  const height = Math.max(1, Math.round(img.height * scale))

  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height

  const ctx = canvas.getContext('2d')
  ctx.drawImage(img, 0, 0, width, height)

  return canvas.toDataURL('image/jpeg', 0.86)
}

async function handleImageSelect(e) {
  const remaining = Math.max(0, 4 - pendingImages.value.length)
  const files = Array.from(e.target.files || []).slice(0, remaining)
  const images = await Promise.all(files.map(async file => {
    const dataUrl = await compressImageFile(file)
    return {
      url: dataUrl,
      dataUrl,
      name: file.name,
    }
  }))
  pendingImages.value.push(...images)
  e.target.value = ''
  showPanel.value = false
}

function removeImage(index) {
  pendingImages.value.splice(index, 1)
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text && !pendingImages.value.length) return

  const images = pendingImages.value.map(i => i.dataUrl)
  inputText.value = ''
  pendingImages.value = []
  showPanel.value = false

  chatStore.sendMessage(text, images)
}

function handleChip(chip) {
  inputText.value = chip
  handleSend()
}

watch(
  () => chatStore.messages.map(m => m.content).join(''),
  async () => {
    await nextTick()
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  }
)

onMounted(() => {
  chatStore.loadHistory()
})
</script>
