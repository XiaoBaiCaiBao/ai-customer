<template>
  <!-- AI 消息 -->
  <div v-if="message.role === 'assistant'" class="flex flex-col items-start gap-1 mb-5 pl-1">
    <div class="relative max-w-[88%] w-full">

      <!-- ── 思考过程面板 ── -->
      <div
        v-if="message.thinkingSteps && message.thinkingSteps.length > 0"
        class="mb-2 rounded-xl overflow-hidden"
        style="background: rgba(255,255,255,0.04); border: 1px solid rgba(255,255,255,0.08);"
      >
        <!-- 折叠标题栏 -->
        <button
          @click="thinkingExpanded = !thinkingExpanded"
          class="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-white/5"
        >
          <!-- 动画脑图标（仍在 streaming 且有步骤时转动） -->
          <span
            class="text-xs"
            :class="message.streaming && !message.content ? 'animate-spin' : ''"
            style="display:inline-block"
          >🧠</span>
          <span class="text-xs font-medium text-white/50 flex-1">
            {{ message.streaming && !message.content ? '思考中…' : `推理过程 · ${message.thinkingSteps.length} 步` }}
          </span>
          <!-- 意图 badge -->
          <span
            v-if="message.intent"
            class="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
            :class="intentBadgeClass(message.intent)"
          >{{ intentLabel(message.intent) }}</span>
          <svg
            class="w-3.5 h-3.5 text-white/30 transition-transform duration-200 flex-shrink-0"
            :class="thinkingExpanded ? 'rotate-180' : ''"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>

        <!-- 步骤列表 -->
        <transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 max-h-0"
          enter-to-class="opacity-100 max-h-[600px]"
          leave-active-class="transition-all duration-150 ease-in"
          leave-from-class="opacity-100 max-h-[600px]"
          leave-to-class="opacity-0 max-h-0"
        >
          <div v-if="thinkingExpanded" class="px-3 pb-3 space-y-2 overflow-hidden">
            <div
              v-for="(step, i) in message.thinkingSteps"
              :key="i"
              class="flex gap-2.5 items-start"
            >
              <!-- 步骤图标 -->
              <div
                class="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] mt-0.5"
                :class="stepIconClass(step.step_type)"
              >
                {{ stepIcon(step.step_type) }}
              </div>

              <!-- 步骤内容 -->
              <div class="flex-1 min-w-0">
                <span
                  class="text-[10px] font-semibold uppercase tracking-wider mr-1.5"
                  :class="stepLabelClass(step.step_type)"
                >{{ stepLabel(step.step_type) }}</span>
                <span
                  class="text-[11px] leading-relaxed break-words"
                  :class="step.step_type === 'action' ? 'font-mono text-emerald-300/80' : 'text-white/55'"
                >{{ step.content }}</span>
              </div>
            </div>

            <!-- 加载动画（仍在流式输出时） -->
            <div v-if="message.streaming && !message.content" class="flex items-center gap-1.5 pl-7">
              <span class="w-1 h-1 rounded-full bg-white/30 animate-bounce" style="animation-delay:0ms"/>
              <span class="w-1 h-1 rounded-full bg-white/30 animate-bounce" style="animation-delay:100ms"/>
              <span class="w-1 h-1 rounded-full bg-white/30 animate-bounce" style="animation-delay:200ms"/>
            </div>
          </div>
        </transition>
      </div>

      <!-- ── 回复气泡 ── -->
      <div
        v-if="message.content || (message.streaming && !(message.thinkingSteps && message.thinkingSteps.length > 0))"
        class="relative px-4 py-3 rounded-tr-2xl rounded-tl-2xl rounded-br-2xl text-[rgba(255,255,255,0.9)] text-sm leading-relaxed backdrop-blur-md"
        :class="{ 'animate-pulse': message.streaming && !message.content }"
        style="background: rgba(92, 95, 255, 0.32); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);"
      >
        <div class="absolute inset-0 rounded-tr-2xl rounded-tl-2xl rounded-br-2xl border border-dashed border-white/20 pointer-events-none" />
        <div class="absolute bottom-0 right-0 w-1/2 h-2/3 rounded-br-2xl bg-gradient-to-tl from-white/5 to-transparent pointer-events-none" />

        <span v-if="message.content && !parsedBullets.length">{{ message.content }}</span>
        <span v-else-if="!message.content" class="text-white/30">...</span>
        <ul v-if="parsedBullets.length" class="mt-2 space-y-2">
          <li v-for="(item, idx) in parsedBullets" :key="idx" class="flex items-start gap-2">
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

  <!-- 用户消息 -->
  <div v-else class="flex flex-col items-end gap-1 mb-5 pr-1">
    <div v-if="message.images?.length" class="flex flex-wrap gap-2 justify-end max-w-[88%]">
      <img
        v-for="(url, i) in message.images"
        :key="i"
        :src="url"
        class="w-32 h-32 rounded-xl object-cover border border-white/10"
      />
    </div>
    <div v-if="message.content" class="relative max-w-[88%]">
      <div
        class="relative px-4 py-3 rounded-2xl text-[rgba(255,255,255,0.9)] text-sm leading-relaxed backdrop-blur-md"
        style="background: rgba(92, 95, 255, 0.18); backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);"
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
import { ref, computed } from 'vue'

const props = defineProps({
  message: { type: Object, required: true },
})

const thinkingExpanded = ref(true)

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

// ── 意图标签 ──
const INTENT_LABELS = {
  product_info: '产品咨询',
  usage_issue:  '问题排查',
  complaint:    '意见反馈',
  aftersales:   '账单售后',
  event:        '活动咨询',
  web_search:   '联网查询',
  chat:         '闲聊',
  unknown:      '未知',
}

function intentLabel(intent) {
  return INTENT_LABELS[intent] || intent
}

function intentBadgeClass(intent) {
  const map = {
    product_info: 'bg-blue-500/20 text-blue-300',
    usage_issue:  'bg-orange-500/20 text-orange-300',
    complaint:    'bg-pink-500/20 text-pink-300',
    aftersales:   'bg-purple-500/20 text-purple-300',
    event:        'bg-teal-500/20 text-teal-300',
    web_search:   'bg-cyan-500/20 text-cyan-300',
    chat:         'bg-gray-500/20 text-gray-300',
    unknown:      'bg-gray-500/20 text-gray-400',
  }
  return map[intent] || 'bg-gray-500/20 text-gray-300'
}

// ── 步骤样式 ──
function stepIcon(type) {
  return { thought: '💭', action: '⚡', observation: '👁', final: '✅' }[type] || '•'
}

function stepIconClass(type) {
  return {
    thought:     'bg-indigo-500/20',
    action:      'bg-emerald-500/20',
    observation: 'bg-amber-500/20',
    final:       'bg-green-500/20',
  }[type] || 'bg-white/10'
}

function stepLabel(type) {
  return { thought: 'Thought', action: 'Action', observation: 'Observation', final: 'Final' }[type] || type
}

function stepLabelClass(type) {
  return {
    thought:     'text-indigo-400',
    action:      'text-emerald-400',
    observation: 'text-amber-400',
    final:       'text-green-400',
  }[type] || 'text-white/40'
}
</script>
