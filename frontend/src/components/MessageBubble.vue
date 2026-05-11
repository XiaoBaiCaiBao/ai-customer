<template>
  <!-- AI 消息 -->
  <div v-if="message.role === 'assistant'" class="flex flex-col items-start gap-1 mb-5 pl-1">
    <div class="relative max-w-[88%] w-full">

      <!-- ── 执行详情面板 ── -->
      <div
        v-if="developerMode && hasExecutionInfo"
        class="mb-2 rounded-xl overflow-hidden"
        style="background: rgba(16,185,129,0.06); border: 1px solid rgba(16,185,129,0.18);"
      >
        <!-- 折叠标题栏 -->
        <button
          @click="thinkingExpanded = !thinkingExpanded"
          class="w-full flex items-center gap-2 px-3 py-2 text-left transition-colors hover:bg-emerald-400/5"
        >
          <span
            class="text-xs"
            :class="message.streaming && !message.content ? 'animate-spin' : ''"
            style="display:inline-block"
          >🛠</span>
          <span class="text-xs font-medium text-emerald-200/70 flex-1">
            {{ message.streaming && !message.content ? `执行详情 · ${currentStepText}` : '执行详情' }}
          </span>
          <span
            v-if="message.intent"
            class="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
            :class="intentBadgeClass(message.intent)"
          >{{ intentLabel(message.intent) }}{{ message.intentConfidence != null ? ` ${formatPercent(message.intentConfidence)}` : '' }}</span>
          <svg
            class="w-3.5 h-3.5 text-emerald-100/30 transition-transform duration-200 flex-shrink-0"
            :class="thinkingExpanded ? 'rotate-180' : ''"
            fill="none" stroke="currentColor" viewBox="0 0 24 24"
          >
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
          </svg>
        </button>

        <transition
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 max-h-0"
          enter-to-class="opacity-100 max-h-[900px]"
          leave-active-class="transition-all duration-150 ease-in"
          leave-from-class="opacity-100 max-h-[900px]"
          leave-to-class="opacity-0 max-h-0"
        >
          <div v-if="thinkingExpanded" class="px-3 pb-3 space-y-2 overflow-hidden text-[11px] leading-relaxed">
            <div
              v-for="item in executionTimeline"
              :key="item.key"
              class="rounded-lg border border-emerald-400/10 bg-black/10 px-2.5 py-2"
            >
              <div class="flex gap-2.5 items-start">
                <div
                  class="flex-shrink-0 w-5 h-5 rounded-full flex items-center justify-center text-[10px] mt-0.5"
                  :class="stepIconClass(item.type)"
                >
                  {{ stepIcon(item.type) }}
                </div>

                <div class="flex-1 min-w-0 space-y-1.5">
                  <div class="flex flex-wrap items-center gap-x-2 gap-y-1">
                    <span
                      class="text-[10px] font-semibold uppercase tracking-wider"
                      :class="stepLabelClass(item.type)"
                    >{{ item.label }}</span>
                    <span v-if="item.title" class="text-white/75 break-words">{{ item.title }}</span>
                    <span
                      v-if="item.status"
                      class="px-1.5 py-0.5 rounded-full text-[10px]"
                      :class="item.status === '失败' ? 'bg-red-500/15 text-red-300/80' : 'bg-emerald-500/15 text-emerald-300/80'"
                    >{{ item.status }}</span>
                  </div>

                  <div v-if="item.input" class="grid grid-cols-[44px_1fr] gap-2 text-white/55">
                    <span class="text-white/35">输入</span>
                    <span class="break-words">{{ item.input }}</span>
                  </div>
                  <div v-if="item.output" class="grid grid-cols-[44px_1fr] gap-2 text-white/55">
                    <span class="text-white/35">输出</span>
                    <span class="break-words">{{ item.output }}</span>
                  </div>
                  <div v-if="item.analysis" class="grid grid-cols-[44px_1fr] gap-2 text-white/45">
                    <span class="text-white/35">说明</span>
                    <span class="break-words">{{ item.analysis }}</span>
                  </div>
                  <div v-if="item.meta?.length" class="flex flex-wrap gap-1.5">
                    <span
                      v-for="meta in item.meta"
                      :key="meta"
                      class="px-1.5 py-0.5 rounded-full bg-white/8 text-white/45"
                    >{{ meta }}</span>
                  </div>
                  <div v-if="item.args" class="space-y-1">
                    <div class="text-white/35">参数</div>
                    <pre class="max-h-28 overflow-auto rounded-md bg-black/20 p-2 text-[10px] text-emerald-200/75 whitespace-pre-wrap break-words">{{ formatJson(item.args) }}</pre>
                  </div>
                  <div v-if="item.result" class="space-y-1">
                    <div class="text-white/35">结果</div>
                    <pre class="max-h-36 overflow-auto rounded-md bg-black/20 p-2 text-[10px] text-white/60 whitespace-pre-wrap break-words">{{ formatJson(item.result) }}</pre>
                  </div>
                </div>
              </div>
            </div>

            <div v-if="!executionTimeline.length && message.streaming" class="pl-7 text-white/40">
              正在等待执行事件…
            </div>

            <div v-if="message.ragResults?.length" class="space-y-1.5 pt-1">
              <div class="text-emerald-300/85 font-semibold">召回片段 · {{ message.ragResults.length }} 条</div>
              <div
                v-for="(item, i) in message.ragResults"
                :key="i"
                class="rounded-lg border border-white/8 bg-black/10 p-2.5 space-y-1.5"
              >
                <div class="flex items-center gap-2 text-[10px] text-white/45">
                  <span class="px-1.5 py-0.5 rounded-full bg-white/6 text-white/55">{{ item.source || '未知来源' }}</span>
                  <span v-if="item.section" class="truncate">{{ item.section }}</span>
                  <span class="ml-auto text-amber-300/75">score {{ formatScore(item.score) }}</span>
                </div>
                <div class="text-[11px] leading-relaxed text-white/70 whitespace-pre-wrap break-words line-clamp-6">
                  {{ item.content }}
                </div>
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
        class="relative w-fit max-w-full px-4 py-3 rounded-tr-2xl rounded-tl-2xl rounded-br-2xl text-[rgba(255,255,255,0.9)] text-sm leading-relaxed backdrop-blur-md"
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
  developerMode: { type: Boolean, default: false },
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

const rewriteOutput = computed(() => {
  if (props.message.rewriteNeedsClarification) {
    return props.message.rewriteClarifyQuestion
      ? `需要澄清：${props.message.rewriteClarifyQuestion}`
      : '需要澄清'
  }
  return props.message.rewriteQuery || ''
})

const hasRewriteInfo = computed(() =>
  Boolean(
    rewriteOutput.value ||
    props.message.rewriteAnalysis ||
    props.message.rewriteQuery
  )
)

const executionTimeline = computed(() => {
  const items = []
  let index = 0

  if (hasRewriteInfo.value) {
    const meta = [
      `历史 ${props.message.rewriteUsedHistory ? '使用' : '未使用'}`,
      `短期记忆 ${props.message.rewriteUsedShortMemory ? '使用' : '未使用'}`,
    ]
    if (props.message.rewriteNeedsClarification) meta.push('需要澄清')

    items.push({
      key: `rewrite-${index++}`,
      type: 'rewrite',
      label: '改写',
      title: props.message.rewriteNeedsClarification ? '需要用户澄清' : '生成标准查询',
      input: props.message.rewriteInput || props.message.userInput || '',
      output: rewriteOutput.value,
      analysis: props.message.rewriteAnalysis || '',
      meta,
    })
  }

  if (props.message.intent || props.message.classification) {
    const classification = props.message.classification || {}
    const intent = props.message.intent || classification.intent
    const confidence = props.message.intentConfidence ?? classification.confidence
    const route = props.message.route || classification.route
    const meta = []
    if (confidence != null) meta.push(`置信度 ${formatScore(confidence)}`)
    if (route) meta.push(`路由 ${route}`)
    if (classification.clarify_question) meta.push(`澄清 ${classification.clarify_question}`)

    items.push({
      key: `classify-${index++}`,
      type: 'classify',
      label: '意图识别',
      title: intent ? `${intentLabel(intent)} (${intent})` : '分类完成',
      input: classification.query || props.message.rewriteQuery || props.message.userInput || '',
      output: route ? `路由到 ${route}` : '',
      meta,
    })
  }

  if (props.message.ragProvider || props.message.ragResults?.length) {
    const count = props.message.ragResultCount || props.message.ragResults?.length || 0
    items.push({
      key: `rag-${index++}`,
      type: 'rag',
      label: '知识库检索',
      title: props.message.ragProvider || 'RAG',
      input: props.message.ragQuery || props.message.rewriteQuery || '',
      output: `召回 ${count} 条`,
      meta: props.message.ragProvider ? [`provider ${props.message.ragProvider}`] : [],
    })
  }

  const usedToolIndexes = new Set()
  const toolCalls = props.message.toolCalls || []
  for (const step of normalizedThinkingSteps.value) {
    const isOutputStep = ['observation', 'final'].includes(step.step_type)
    items.push({
      key: `step-${index++}`,
      type: step.step_type,
      label: stepLabel(step.step_type),
      title: isOutputStep ? '' : step.content,
      output: isOutputStep ? step.content : '',
      meta: step.step_num != null ? [`step ${step.step_num}`] : [],
    })

    const taskId = extractTaskId(step.content)
    if (!taskId) continue
    toolCalls.forEach((tool, toolIndex) => {
      if (usedToolIndexes.has(toolIndex) || tool.taskId !== taskId) return
      items.push(toolCallItem(tool, `tool-${index++}`))
      usedToolIndexes.add(toolIndex)
    })
  }

  toolCalls.forEach((tool, toolIndex) => {
    if (usedToolIndexes.has(toolIndex)) return
    items.push(toolCallItem(tool, `tool-${index++}`))
  })

  return items
})

const currentStepText = computed(() => {
  const last = executionTimeline.value[executionTimeline.value.length - 1]
  if (!last) return '准备中'
  return `${last.label}${last.title ? `：${last.title}` : ''}`
})

const hasExecutionInfo = computed(() =>
  Boolean(
    executionTimeline.value.length ||
    props.message.thinkingSteps?.length ||
    props.message.toolCalls?.length ||
    rewriteOutput.value ||
    props.message.rewriteQuery ||
    props.message.rewriteAnalysis ||
    props.message.intent ||
    props.message.intentConfidence != null ||
    props.message.route ||
    props.message.classification ||
    props.message.ragResults?.length ||
    props.message.ragProvider
  )
)

const normalizedThinkingSteps = computed(() =>
  (props.message.thinkingSteps || []).filter((step) => !isDuplicateStep(step))
)

function isDuplicateStep(step) {
  const type = step.step_type
  const content = step.content || ''
  if (['rewrite', 'thought', 'route'].includes(type)) return true
  if (content.startsWith('MCP.') || content.startsWith('MCP 返回')) return true
  if (content.startsWith('KnowledgeBase.search') || content.startsWith('检索到 ') || content.includes('知识库中未找到')) return true
  return false
}

function extractTaskId(content = '') {
  const match = content.match(/^\[(T\d+)\]/)
  return match ? match[1] : ''
}

function toolCallItem(tool, key) {
  const logical = tool.logicalToolName && tool.logicalToolName !== tool.toolName
    ? ` / ${tool.logicalToolName}`
    : ''
  const meta = []
  if (tool.node) meta.push(`node ${tool.node}`)
  if (tool.taskId) meta.push(`task ${tool.taskId}`)
  if (tool.branch) meta.push(`branch ${tool.branch}`)
  if (tool.observation) meta.push(tool.observation)

  return {
    key,
    type: 'tool',
    label: '工具调用',
    title: `${tool.toolName || 'unknown'}${logical}`,
    status: tool.success ? '成功' : '失败',
    output: tool.error?.message || '',
    args: tool.arguments || {},
    result: tool.result || tool.error || null,
    meta,
  }
}

// ── 意图标签 ──
const INTENT_LABELS = {
  usage_guide: '使用指南',
  account_issue_consult: '账号问题',
  feature_play_consult: '功能玩法',
  privacy_permission_consult: '隐私权限',
  activity_consult: '活动咨询',
  content_safety_consult: '内容安全',
  chat_quality_feedback: '聊天质量',
  pre_sales_consult: '售前咨询',
  after_sales_issue: '售后问题',
  product_suggestion: '产品建议',
  product_complaint: '产品吐槽',
  fault_feedback: '故障反馈',
  chat_respond: '闲聊',
  unknown_respond: '未知',
}

function intentLabel(intent) {
  return INTENT_LABELS[intent] || intent
}

function intentBadgeClass(intent) {
  const map = {
    usage_guide: 'bg-blue-500/20 text-blue-300',
    account_issue_consult: 'bg-sky-500/20 text-sky-300',
    feature_play_consult: 'bg-indigo-500/20 text-indigo-300',
    privacy_permission_consult: 'bg-cyan-500/20 text-cyan-300',
    activity_consult: 'bg-teal-500/20 text-teal-300',
    content_safety_consult: 'bg-amber-500/20 text-amber-300',
    chat_quality_feedback: 'bg-fuchsia-500/20 text-fuchsia-300',
    pre_sales_consult: 'bg-emerald-500/20 text-emerald-300',
    after_sales_issue: 'bg-purple-500/20 text-purple-300',
    product_suggestion: 'bg-lime-500/20 text-lime-300',
    product_complaint: 'bg-pink-500/20 text-pink-300',
    fault_feedback: 'bg-orange-500/20 text-orange-300',
    chat_respond: 'bg-gray-500/20 text-gray-300',
    unknown_respond: 'bg-gray-500/20 text-gray-400',
  }
  return map[intent] || 'bg-gray-500/20 text-gray-300'
}

// ── 步骤样式 ──
function stepIcon(type) {
  return { rewrite: 'R', classify: 'C', rag: 'K', tool: 'M', thought: 'T', route: '↳', action: 'A', observation: 'O', final: 'F' }[type] || '•'
}

function stepIconClass(type) {
  return {
    rewrite:     'bg-violet-500/20',
    classify:    'bg-indigo-500/20',
    rag:         'bg-sky-500/20',
    tool:        'bg-emerald-500/20',
    thought:     'bg-indigo-500/20',
    route:       'bg-cyan-500/20',
    action:      'bg-emerald-500/20',
    observation: 'bg-amber-500/20',
    final:       'bg-green-500/20',
  }[type] || 'bg-white/10'
}

function stepLabel(type) {
  return { rewrite: 'Rewrite', classify: 'Classify', rag: 'Retrieve', tool: 'MCP Tool', thought: 'Classify', route: 'Route', action: 'Step', observation: 'Result', final: 'Reply' }[type] || type
}

function stepLabelClass(type) {
  return {
    rewrite:     'text-violet-400',
    classify:    'text-indigo-400',
    rag:         'text-sky-400',
    tool:        'text-emerald-400',
    thought:     'text-indigo-400',
    route:       'text-cyan-400',
    action:      'text-emerald-400',
    observation: 'text-amber-400',
    final:       'text-green-400',
  }[type] || 'text-white/40'
}

function formatScore(score) {
  const n = Number(score)
  if (Number.isNaN(n)) return '-'
  return n.toFixed(4)
}

function formatPercent(score) {
  const n = Number(score)
  if (Number.isNaN(n)) return ''
  return `${Math.round(n * 100)}%`
}

function formatJson(value) {
  if (value == null) return ''
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value, null, 2)
  } catch {
    return String(value)
  }
}
</script>
