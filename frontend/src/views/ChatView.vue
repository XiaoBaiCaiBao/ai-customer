<template>
  <div class="flex flex-col h-screen bg-surface text-white max-w-md mx-auto relative">

    <!-- Header -->
    <header class="flex items-center justify-between px-5 py-4 border-b border-surface-border flex-shrink-0">
      <div class="flex items-center gap-3">
        <button class="text-gray-400 hover:text-white transition-colors">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
          </svg>
        </button>
        <span class="font-bold text-lg tracking-wider">BOU</span>
      </div>

      <div class="flex items-center gap-3">
        <!-- AI 状态指示器 -->
        <div class="flex items-center gap-1.5 text-xs font-medium">
          <span class="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
          <span class="text-green-400">AI ACTIVE</span>
        </div>
        <!-- 头像 -->
        <div class="w-8 h-8 rounded-full bg-accent flex items-center justify-center text-xs font-bold">
          AI
        </div>
      </div>
    </header>

    <!-- 消息列表 -->
    <div
      ref="scrollRef"
      class="flex-1 overflow-y-auto px-4 py-4 space-y-1"
    >
      <!-- 日期分割线 -->
      <div class="flex items-center justify-center my-3">
        <span class="text-xs text-gray-600 bg-surface-card px-3 py-1 rounded-full border border-surface-border">
          TODAY
        </span>
      </div>

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
          BOU Intelligence
        </span>
        <div class="flex items-center gap-1.5 px-4 py-3 bg-surface-card border border-surface-border rounded-2xl rounded-tl-sm w-fit">
          <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:0ms" />
          <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:150ms" />
          <span class="w-1.5 h-1.5 rounded-full bg-gray-400 animate-bounce" style="animation-delay:300ms" />
          <span class="text-xs text-gray-500 ml-1">BOU IS THINKING</span>
        </div>
      </div>
    </div>

    <!-- 快捷操作 chips -->
    <div class="px-4 pb-2 flex gap-2 overflow-x-auto flex-shrink-0 scrollbar-hide">
      <button
        v-for="chip in quickChips"
        :key="chip"
        @click="handleChip(chip)"
        class="flex-shrink-0 text-xs px-3 py-1.5 rounded-full border border-surface-border bg-surface-card text-gray-300 hover:border-accent hover:text-white transition-colors whitespace-nowrap"
      >
        {{ chip }}
      </button>
    </div>

    <!-- 输入栏 -->
    <div class="px-4 py-3 border-t border-surface-border flex-shrink-0">
      <div class="flex items-center gap-3 bg-surface-card border border-surface-border rounded-2xl px-4 py-2.5">
        <button class="text-gray-500 hover:text-white transition-colors flex-shrink-0">
          <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
          </svg>
        </button>

        <input
          v-model="inputText"
          @keydown.enter.prevent="handleSend"
          type="text"
          placeholder="Whisper your query..."
          class="flex-1 bg-transparent text-sm text-gray-200 placeholder-gray-600 outline-none"
          :disabled="chatStore.isThinking"
        />

        <button
          @click="handleSend"
          :disabled="!inputText.trim() || chatStore.isThinking"
          class="flex-shrink-0 w-8 h-8 rounded-full bg-accent hover:bg-accent-hover disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center justify-center"
        >
          <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 24 24">
            <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
          </svg>
        </button>
      </div>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, nextTick, watch, onMounted } from 'vue'
import { useChatStore } from '../stores/chat'
import MessageBubble from '../components/MessageBubble.vue'

const chatStore = useChatStore()
const inputText = ref('')
const scrollRef = ref(null)

const welcomeMessage = {
  role: 'assistant',
  content: 'Greetings. I am your Celestial guide for BOU. How may I assist your digital journey today?',
  id: 'welcome',
  streaming: false,
}

const quickChips = [
  '会员权益',
  '账户安全',
  '积分问题',
  '充值问题',
  '产品建议',
]

const hasStreamingMessage = computed(() =>
  chatStore.messages.some(m => m.streaming)
)

function handleSend() {
  const text = inputText.value.trim()
  if (!text) return
  inputText.value = ''
  chatStore.sendMessage(text)
}

function handleChip(chip) {
  inputText.value = chip
  handleSend()
}

// 有新消息时自动滚到底部
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
