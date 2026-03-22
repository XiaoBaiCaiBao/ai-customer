import { defineStore } from 'pinia'
import { ref } from 'vue'

/** 与后端 ChatRequest.user_id 一致；多用户时在登录后设置 localStorage.chat_user_id */
function readUserId() {
  return localStorage.getItem('chat_user_id') || 'demo_user'
}

function getAuthHeaders() {
  const token = localStorage.getItem('chat_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

function sessionStorageKey(userId) {
  return `chat_session_id_${userId}`
}

function initialSessionId(userId) {
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

  function refreshUser() {
    userId.value = readUserId()
    sessionId.value = initialSessionId(userId.value) || null
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
      intent: null,
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

  function finalizeMessage(index) {
    if (messages.value[index]) {
      messages.value[index].streaming = false
    }
  }

  async function sendMessage(text, images = []) {
    if (!text.trim() && !images.length) return
    if (isThinking.value) return

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
        }),
      })

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
            } else if (data.type === 'thinking_step') {
              appendThinkingStep(msgIndex, {
                step_type: data.step_type,
                step_num: data.step_num,
                content: data.content,
              })
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
      const data = await res.json()
      messages.value = data.messages.map((m, i) => ({
        ...m,
        id: i,
        thinkingSteps: [],
        intent: null,
      }))
    } catch {
      // 静默失败
    }
  }

  async function clearHistory() {
    if (!sessionId.value) return
    const q = new URLSearchParams({
      session_id: sessionId.value,
    })
    await fetch(`/api/chat/history?${q}`, { 
      method: 'DELETE',
      headers: getAuthHeaders()
    })
    messages.value = []
    sessionId.value = null
    localStorage.removeItem(sessionStorageKey(userId.value))
  }

  return {
    messages,
    userId,
    sessionId,
    isThinking,
    currentIntent,
    sendMessage,
    loadHistory,
    clearHistory,
    refreshUser,
  }
})
