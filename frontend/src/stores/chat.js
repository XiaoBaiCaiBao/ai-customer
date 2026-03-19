import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChatStore = defineStore('chat', () => {
  const messages = ref([])
  const sessionId = ref(localStorage.getItem('chat_session_id') || null)
  const isThinking = ref(false)
  const currentIntent = ref(null)

  function addUserMessage(content) {
    messages.value.push({ role: 'user', content, id: Date.now() })
  }

  function startAssistantMessage() {
    const msg = { role: 'assistant', content: '', id: Date.now(), streaming: true }
    messages.value.push(msg)
    return messages.value.length - 1
  }

  function appendToken(index, token) {
    if (messages.value[index]) {
      messages.value[index].content += token
    }
  }

  function finalizeMessage(index) {
    if (messages.value[index]) {
      messages.value[index].streaming = false
    }
  }

  async function sendMessage(text) {
    if (!text.trim() || isThinking.value) return

    addUserMessage(text)
    isThinking.value = true
    currentIntent.value = null

    const msgIndex = startAssistantMessage()

    try {
      const response = await fetch('/api/chat/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          session_id: sessionId.value,
          user_id: 'demo_user',
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
              localStorage.setItem('chat_session_id', data.session_id)
            } else if (data.type === 'token') {
              appendToken(msgIndex, data.content)
            } else if (data.type === 'intent') {
              currentIntent.value = data.intent
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
      const res = await fetch(`/api/chat/history?session_id=${sessionId.value}`)
      const data = await res.json()
      messages.value = data.messages.map((m, i) => ({ ...m, id: i }))
    } catch {
      // 静默失败
    }
  }

  async function clearHistory() {
    if (!sessionId.value) return
    await fetch(`/api/chat/history?session_id=${sessionId.value}`, { method: 'DELETE' })
    messages.value = []
    sessionId.value = null
    localStorage.removeItem('chat_session_id')
  }

  return {
    messages,
    sessionId,
    isThinking,
    currentIntent,
    sendMessage,
    loadHistory,
    clearHistory,
  }
})
