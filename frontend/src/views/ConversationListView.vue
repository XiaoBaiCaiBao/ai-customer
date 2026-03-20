<template>
  <div class="min-h-screen bg-[#1d1d22] flex flex-col relative overflow-hidden">

    <AppHeader title="消息列表"></AppHeader>

    <!-- 会话列表 -->
    <main class="flex-1 relative z-10 px-4 py-5 flex flex-col gap-4 max-w-lg mx-auto w-full">
      <button
        v-for="item in conversations"
        :key="item.id"
        class="w-full text-left rounded-full bg-[#27272E] flex items-center gap-3 pl-4 pr-6 py-3 transition-opacity hover:opacity-80 active:opacity-60"
        @click="goToChat(item)"
      >
        <!-- 头像 -->
        <div class="w-14 h-14 rounded-full border border-[rgba(152,154,255,0.5)] overflow-hidden shrink-0">
          <img v-if="item.avatar" :src="item.avatar" :alt="item.name" class="w-full h-full object-cover" />
          <div v-else class="w-full h-full flex items-center justify-center" :style="{ background: item.avatarBg }">
            <span class="text-2xl">{{ item.avatarEmoji }}</span>
          </div>
        </div>

        <!-- 右侧内容 -->
        <div class="flex-1 min-w-0 flex flex-col gap-2">
          <!-- 第一行：名称 + 状态标签 + 未读数 -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <span class="text-white font-medium text-sm leading-none">{{ item.name }}</span>
              <span
                class="text-xs px-2 py-0.5 rounded-full border leading-none"
                :class="item.matched ? 'border-[#999bff] text-[#999bff]' : 'border-white/10 text-white/30'"
              >{{ item.matched ? '已匹配' : '未匹配' }}</span>
            </div>
            <span
              v-if="item.unread"
              class="bg-[#e9405f] text-white text-xs leading-none px-2 py-0.5 rounded-full shrink-0"
            >{{ item.unread }}</span>
          </div>

          <!-- 分割线 -->
          <img :src="divider" alt="" class="w-full h-auto" aria-hidden="true" />

          <!-- 第二行：最新消息 + 时间 -->
          <div class="flex items-center justify-between gap-3">
            <p
              class="flex-1 text-xs truncate leading-none"
              :class="item.matched ? 'text-[rgba(255,214,100,0.7)]' : 'text-white/50'"
            >{{ item.lastMsg }}</p>
            <span class="text-xs text-white/30 shrink-0">{{ item.time }}</span>
          </div>
        </div>
      </button>
    </main>

    <!-- 底部导航栏 -->
    <nav class="relative z-10 bg-[#222228] border-t border-white/10 shrink-0">
      <div class="flex items-center justify-around py-4 max-w-lg mx-auto">
        <!-- 消息（当前激活） -->
        <button class="flex flex-col items-center gap-2 group">
          <svg class="w-7 h-7 text-[#999bff]" viewBox="0 0 28 28" fill="none">
            <path d="M4 6C4 4.895 4.895 4 6 4H22C23.105 4 24 4.895 24 6V17C24 18.105 23.105 19 22 19H15L10 24V19H6C4.895 19 4 18.105 4 17V6Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
            <path d="M9 10H19M9 13.5H15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span class="text-xs text-[#999bff]">消息</span>
        </button>
        <!-- 动态 -->
        <button class="flex flex-col items-center gap-2 text-white/50 hover:text-white/80 transition-colors">
          <svg class="w-7 h-7" viewBox="0 0 28 28" fill="none">
            <path d="M14 4L15.8 9.6L22 9.6L17.1 13.2L18.9 18.8L14 15.2L9.1 18.8L10.9 13.2L6 9.6L12.2 9.6L14 4Z" stroke="currentColor" stroke-width="1.5" stroke-linejoin="round"/>
          </svg>
          <span class="text-xs">动态</span>
        </button>
        <!-- 个人 -->
        <button class="flex flex-col items-center gap-2 text-white/50 hover:text-white/80 transition-colors" @click="goToLogin">
          <svg class="w-7 h-7" viewBox="0 0 28 28" fill="none">
            <circle cx="14" cy="10" r="4" stroke="currentColor" stroke-width="1.5"/>
            <path d="M6 23C6 19.134 9.134 16 13 16H15C18.866 16 22 19.134 22 23" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
          <span class="text-xs">个人</span>
        </button>
      </div>
    </nav>

  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import AppHeader from '../components/AppHeader.vue'
import divider from '../assets/conversation/divider.png'
import filterIcon from '../assets/conversation/filter-icon.svg'
import avatarLinyu from '../assets/conversation/avatar-linyu.png'

const router = useRouter()

const conversations = [
  {
    id: 1,
    name: 'Rafayel',
    matched: false,
    unread: 88,
    avatar: avatarLinyu,
    avatarBg: null,
    avatarEmoji: null,
    lastMsg: '你好，我叫Rafayel',
    time: '16:38',
  },
  {
    id: 2,
    name: 'AI助手',
    matched: true,
    unread: 3,
    avatar: null,
    avatarBg: 'linear-gradient(135deg, #5c5fff 0%, #999bff 100%)',
    avatarEmoji: '🤖',
    lastMsg: '有什么我可以帮助您的吗？',
    time: '10:05',
  },
]

function goToChat(item) {
  router.push({ path: '/chat', query: { agent: item.id === 1 ? 'rafayel' : 'ai' } })
}

function goToLogin() {
  router.push('/login')
}
</script>
