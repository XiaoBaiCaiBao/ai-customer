<template>
  <!-- AI 消息：深色背景，三角圆角（左上直角），虚线边框 -->
  <div v-if="message.role === 'assistant'" class="flex flex-col items-start gap-1 mb-5 pl-1">
    <div class="relative max-w-[88%]">
      <div
        class="relative px-4 py-3 rounded-tr-2xl rounded-tl-2xl rounded-br-2xl text-[rgba(255,255,255,0.9)] text-sm leading-relaxed"
        :class="{ 'animate-pulse': message.streaming && !message.content }"
        style="background: #5C5FFF;"
      >
        <!-- 虚线边框（排除左下角） -->
        <div class="absolute inset-0 rounded-tr-2xl rounded-tl-2xl rounded-br-2xl border border-dashed border-white/20 pointer-events-none" />
        <!-- 右下角光晕装饰 -->
        <div class="absolute bottom-0 right-0 w-1/2 h-2/3 rounded-br-2xl bg-gradient-to-tl from-white/5 to-transparent pointer-events-none" />

        <!-- 内容 -->
        <span v-if="message.content && !parsedBullets.length">{{ message.content }}</span>
        <span v-else-if="!message.content" class="text-white/30">...</span>
        <ul v-if="parsedBullets.length" class="mt-2 space-y-2">
          <li v-for="(item, i) in parsedBullets" :key="i" class="flex items-start gap-2">
            <span class="mt-0.5 text-[#999bff] flex-shrink-0">✦</span>
            <div>
              <span class="font-semibold text-white">{{ item.title }}</span>
              <span class="text-white/60"> {{ item.desc }}</span>
            </div>
          </li>
        </ul>
      </div>
    </div>
    <span class="text-xs text-white/25 px-1">{{ timeStr }}</span>
  </div>

  <!-- 用户消息：蓝紫半透明，backdrop-blur，虚线边框，全圆角 -->
  <div v-else class="flex flex-col items-end gap-1 mb-5 pr-1">
    <!-- 图片预览 -->
    <div v-if="message.images?.length" class="flex flex-wrap gap-2 justify-end max-w-[88%]">
      <img
        v-for="(url, i) in message.images"
        :key="i"
        :src="url"
        class="w-32 h-32 rounded-xl object-cover border border-white/10"
      />
    </div>
    <!-- 文字气泡（无文字时不渲染） -->
    <div v-if="message.content" class="relative max-w-[88%]">
      <div
        class="relative px-4 py-3 rounded-2xl text-[rgba(255,255,255,0.9)] text-sm leading-relaxed backdrop-blur-md"
        style="background: rgba(92, 95, 255, 0.18);"
      >
        <div class="absolute inset-0 rounded-2xl border border-dashed border-white/25 pointer-events-none" />
        <div class="absolute top-0 left-0 w-1/3 h-1/2 rounded-tl-2xl bg-gradient-to-br from-white/8 to-transparent pointer-events-none" />
        {{ message.content }}
      </div>
    </div>
    <span class="text-xs text-white/25 px-1">{{ timeStr }}</span>
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

const parsedBullets = computed(() => {
  if (!props.message.content || props.message.streaming) return []
  const lines = props.message.content.split('\n')
  const bullets = []
  for (const line of lines) {
    const match = line.match(/^[•\-\*]\s+\*\*(.+?)\*\*[：:]\s*(.+)$/)
    if (match) bullets.push({ title: match[1], desc: match[2] })
  }
  return bullets
})
</script>
