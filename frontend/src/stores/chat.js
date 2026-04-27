import { defineStore } from 'pinia'
import { ref } from 'vue'
import { ALLOWED_USER_ID, clearLocalAuth } from '../utils/auth'

/** 与后端 ChatRequest.user_id 一致；多用户时在登录后设置 localStorage.chat_user_id */
function readUserId() {
  return localStorage.getItem('chat_user_id') || ''
}

function getAuthHeaders() {
  const token = localStorage.getItem('chat_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function ensureAuthorizedResponse(response) {
  if (response.status === 401 || response.status === 403) {
    clearLocalAuth()
    window.location.href = '/'
    throw new Error('unauthorized')
  }
  if (!response.ok) {
    let detail = '请求失败'
    try {
      const data = await response.json()
      detail = data?.detail || data?.message || detail
    } catch {
      // ignore
    }
    throw new Error(detail)
  }
}

function sessionStorageKey(userId) {
  return `chat_session_id_${userId || 'guest'}`
}

function initialSessionId(userId) {
  if (!userId) return null
  const k = sessionStorageKey(userId)
  let sid = localStorage.getItem(k)
  if (!sid) {
    const legacy = localStorage.getItem('chat_session_id')
    if (legacy) {
      localStorage.setItem(k, legacy)
      localStorage.removeItem('chat_session_id')
      sid = legacy
    }
  }
  return sid
}

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const userId = ref(readUserId())
  const sessionId = ref(initialSessionId(userId.value) || null)
  const isThinking = ref(false)
  const currentIntent = ref(null)
  const developerMode = ref(localStorage.getItem('chat_developer_mode') === '1')

  function refreshUser() {
    userId.value = readUserId()
    sessionId.value = initialSessionId(userId.value) || null
  }

  function resetSessionState() {
    messages.value = []
    sessionId.value = null
    currentIntent.value = null
  }

  function addUserMessage(content, images = []) {
    messages.value.push({ role: 'user', content, images, id: Date.now() })
  }

  function startAssistantMessage() {
    const msg = {
      role: 'assistant',
      content: '',
      id: Date.now(),
      streaming: true,
      thinkingSteps: [],  // 思考步骤列表
      ragResults: [],
      intent: null,
      rewrittenQuery: '',
      ragProvider: '',
      ragResultCount: 0,
    }
    messages.value.push(msg)
    return messages.value.length - 1
  }

  function appendToken(index, token) {
    if (messages.value[index]) {
      messages.value[index].content += token
    }
  }

  function appendThinkingStep(index, step) {
    if (messages.value[index]) {
      messages.value[index].thinkingSteps.push(step)
    }
  }

  function setMessageIntent(index, intent) {
    if (messages.value[index]) {
      messages.value[index].intent = intent
    }
  }

  function setRagResults(index, query, results) {
    if (messages.value[index]) {
      messages.value[index].ragQuery = query
      messages.value[index].ragResults = results
    }
  }

  function setRewrittenQuery(index, rewrittenQuery) {
    if (messages.value[index]) {
      messages.value[index].rewrittenQuery = rewrittenQuery
    }
  }

  function setRagMeta(index, payload) {
    if (messages.value[index]) {
      messages.value[index].ragProvider = payload.provider || ''
      messages.value[index].ragQuery = payload.query || messages.value[index].ragQuery
      messages.value[index].ragResultCount = payload.result_count || 0
    }
  }

  function toggleDeveloperMode() {
    developerMode.value = !developerMode.value
    localStorage.setItem('chat_developer_mode', developerMode.value ? '1' : '0')
  }

  function finalizeMessage(index) {
    if (messages.value[index]) {
      messages.value[index].streaming = false
    }
  }

  async function sendMessage(text, images = []) {
    if (!text.trim() && !images.length) return
    if (isThinking.value) return
    if (userId.value !== ALLOWED_USER_ID) return

    addUserMessage(text, images)
    isThinking.value = true
    currentIntent.value = null

    const msgIndex = startAssistantMessage()

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        body: JSON.stringify({
          message: text,
          session_id: sessionId.value,
          images,
        }),
      })
      if (response.status === 401 || response.status === 403) {
        clearLocalAuth()
        resetSessionState()
        userId.value = ''
        window.location.href = '/'
        return
      }
      if (!response.ok) {
        throw new Error('发送失败')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const lines = decoder.decode(value).split('\n')
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const data = JSON.parse(line.slice(6))

            if (data.type === 'session' && !sessionId.value) {
              sessionId.value = data.session_id
              localStorage.setItem(sessionStorageKey(userId.value), data.session_id)
            } else if (data.type === 'token') {
              appendToken(msgIndex, data.content)
            } else if (data.type === 'intent') {
              currentIntent.value = data.intent
              setMessageIntent(msgIndex, data.intent)
            } else if (data.type === 'rewrite') {
              setRewrittenQuery(msgIndex, data.rewritten_query)
            } else if (data.type === 'thinking_step') {
              appendThinkingStep(msgIndex, {
                step_type: data.step_type,
                step_num: data.step_num,
                content: data.content,
              })
            } else if (data.type === 'rag_meta') {
              setRagMeta(msgIndex, data)
            } else if (data.type === 'rag_results') {
              setRagResults(msgIndex, data.query, data.results || [])
            } else if (data.type === 'done') {
              finalizeMessage(msgIndex)
            }
          } catch {
            // 忽略解析异常
          }
        }
      }
    } catch (e) {
      appendToken(msgIndex, '抱歉，连接出现问题，请稍后重试。')
      finalizeMessage(msgIndex)
    } finally {
      isThinking.value = false
    }
  }

  async function loadHistory() {
    if (!sessionId.value) return
    try {
      const q = new URLSearchParams({
        session_id: sessionId.value,
      })
      const res = await fetch(`/api/chat/history?${q}`, {
        headers: getAuthHeaders()
      })
      if (res.status === 401 || res.status === 403) {
        clearLocalAuth()
        resetSessionState()
        userId.value = ''
        window.location.href = '/'
        return
      }
      if (!res.ok) return
      const data = await res.json()
      messages.value = data.messages.map((m, i) => ({
        ...m,
        id: i,
        thinkingSteps: [],
        ragResults: [],
        intent: null,
        rewrittenQuery: '',
        ragProvider: '',
        ragResultCount: 0,
      }))
    } catch {
      // 静默失败
    }
  }

  async function clearHistory() {
    if (sessionId.value) {
      const q = new URLSearchParams({
        session_id: sessionId.value,
      })
      const res = await fetch(`/api/chat/history?${q}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      })
      await ensureAuthorizedResponse(res)
    }
    resetSessionState()
    localStorage.removeItem(sessionStorageKey(userId.value))
  }

  async function resetChat() {
    const res = await fetch('/api/chat/reset', {
      method: 'DELETE',
      headers: getAuthHeaders()
    })
    await ensureAuthorizedResponse(res)
    resetSessionState()
    localStorage.removeItem(sessionStorageKey(userId.value))
  }

  return {
    messages,
    userId,
    sessionId,
    isThinking,
    currentIntent,
    developerMode,
    sendMessage,
    loadHistory,
    clearHistory,
    resetChat,
    refreshUser,
    resetSessionState,
    toggleDeveloperMode,
  }
})
