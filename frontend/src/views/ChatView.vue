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
    <AppHeader title="AI助手" :show-back="true"></AppHeader>

    <!-- 消息列表 -->
    <div
      ref="scrollRef"
      class="flex-1 overflow-y-auto px-4 py-4 space-y-1 relative z-10"
    >
      <!-- 欢迎消息 -->
      <MessageBubble
        v-if="chatStore.messages.length === 0"
        :message="welcomeMessage"
      />

      <!-- 对话消息 -->
      <MessageBubble
        v-for="msg in chatStore.messages"
        :key="msg.id"
        :message="msg"
      />

      <!-- 思考中动画 -->
      <div v-if="chatStore.isThinking && !hasStreamingMessage" class="flex flex-col gap-1 mb-4">
        <span class="text-xs font-semibold tracking-widest text-gray-500 uppercase px-1">
          AI助手
        </span>
        <div class="flex items-center gap-1.5 px-4 py-3 bg-surface-card border border-surface-border rounded-2xl rounded-tl-sm w-fit">
          <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:0ms" />
          <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:150ms" />
          <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:300ms" />
          <span class="text-xs text-gray-500 ml-1">思考中...</span>
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
    </div>

    <!-- 更多 Panel（从底部滑入） -->
    <transition
      enter-active-class="transition-all duration-300 ease-out"
      enter-from-class="translate-y-full opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition-all duration-200 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="translate-y-full opacity-0"
    >
      <div v-if="showPanel" class="flex-shrink-0 border-surface-border px-6 pt-1 relative z-10">
        <div class="flex gap-6">
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

          <!-- 重启（预留） -->
          <button class="flex flex-col items-center gap-2 group opacity-50 cursor-not-allowed">
            <div class="w-14 h-14 rounded-2xl bg-surface-card border border-surface-border flex items-center justify-center">
              <svg class="w-6 h-6 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
              </svg>
            </div>
            <span class="text-xs text-gray-500">重启</span>
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
import { useRoute } from 'vue-router'
import { useChatStore } from '../stores/chat'
import AppHeader from '../components/AppHeader.vue'
import MessageBubble from '../components/MessageBubble.vue'
import bgImage from '../assets/common/Rafayel.webp'

const route = useRoute()
const isRafayel = computed(() => route.query.agent === 'rafayel')

const chatStore = useChatStore()
const inputText = ref('')
const scrollRef = ref(null)
const showPanel = ref(false)
const fileInputRef = ref(null)
const pendingImages = ref([]) // [{ url: string, file: File }]

const welcomeMessage = {
  role: 'assistant',
  content: '你好，我是你的AI助手，有什么可以帮你的吗？',
  id: 'welcome',
  streaming: false,
}

const quickChips = ['会员权益', '账户安全', '积分问题', '充值问题', '产品建议']

const hasStreamingMessage = computed(() =>
  chatStore.messages.some(m => m.streaming)
)

function togglePanel() {
  showPanel.value = !showPanel.value
}

function triggerImageUpload() {
  fileInputRef.value?.click()
}

function handleImageSelect(e) {
  const files = Array.from(e.target.files || [])
  files.forEach(file => {
    const url = URL.createObjectURL(file)
    pendingImages.value.push({ url, file })
  })
  e.target.value = ''
  showPanel.value = false
}

function removeImage(index) {
  URL.revokeObjectURL(pendingImages.value[index].url)
  pendingImages.value.splice(index, 1)
}

function handleSend() {
  const text = inputText.value.trim()
  if (!text && !pendingImages.value.length) return

  // 将图片 URL 列表传入消息（仅展示用，后续可扩展为 base64 上传）
  const images = pendingImages.value.map(i => i.url)
  inputText.value = ''
  pendingImages.value.forEach(i => { /* 不revoke，消息气泡中还要展示 */ })
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
