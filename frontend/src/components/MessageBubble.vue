<template>
  <!-- AI 消息 -->
  <div v-if="message.role === 'assistant'" class="flex flex-col gap-1 mb-5">
    <span class="text-xs font-semibold tracking-widest text-gray-500 uppercase px-1">
      BOU Intelligence
    </span>
    <div class="relative max-w-[85%]">
      <div
        class="bg-surface-card border border-surface-border rounded-2xl rounded-tl-sm px-4 py-3 text-sm leading-relaxed text-gray-200"
        :class="{ 'animate-pulse': message.streaming && !message.content }"
      >
        <!-- 正在流式输出时显示内容 + 光标（有 bullet 解析时隐藏原文） -->
        <span v-if="message.content && !parsedBullets.length">{{ message.content }}</span>
        <span v-else-if="!message.content" class="text-gray-500">...</span>
        <span
          v-if="message.streaming"
          class="inline-block w-0.5 h-3.5 bg-accent-light ml-0.5 animate-pulse align-middle"
        />

        <!-- 结构化内容：带 bullet 的列表 -->
        <ul v-if="parsedBullets.length" class="mt-2 space-y-2">
          <li
            v-for="(item, i) in parsedBullets"
            :key="i"
            class="flex items-start gap-2"
          >
            <span class="mt-0.5 text-accent-light flex-shrink-0">{{ item.icon }}</span>
            <div>
              <span class="font-semibold text-white">{{ item.title }}</span>
              <span class="text-gray-400"> {{ item.desc }}</span>
            </div>
          </li>
        </ul>
      </div>
    </div>
    <span class="text-xs text-gray-600 px-1">{{ timeStr }}</span>
  </div>

  <!-- 用户消息 -->
  <div v-else class="flex flex-col items-end gap-1 mb-5">
    <div class="max-w-[80%]">
      <div class="bg-accent rounded-2xl rounded-tr-sm px-4 py-3 text-sm leading-relaxed text-white">
        {{ message.content }}
      </div>
    </div>
    <span class="text-xs text-gray-600 px-1">{{ timeStr }}</span>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
})

const timeStr = computed(() => {
  const d = new Date()
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
})

// 简单解析「**Bold:** desc」格式，用于 RAG 返回的结构化内容
const parsedBullets = computed(() => {
  if (!props.message.content || props.message.streaming) return []
  const lines = props.message.content.split('\n')
  const bullets = []
  for (const line of lines) {
    const match = line.match(/^[•\-\*]\s+\*\*(.+?)\*\*[：:]\s*(.+)$/)
    if (match) {
      bullets.push({ icon: '✦', title: match[1], desc: match[2] })
    }
  }
  return bullets
})
</script>
