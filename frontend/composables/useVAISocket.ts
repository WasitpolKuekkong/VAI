export interface ChatMessage {
  id: number
  role: 'user' | 'ai' | 'error'
  text: string
  elapsed?: number
  fromVoice?: boolean
}

export interface ServerStatus {
  backend: string
  lmstudio_url: string
  lmstudio_healthy: boolean
  gemini_model: string
  lmstudio_model: string
  audio_enabled: boolean
}

export const useVAISocket = () => {
  const messages = ref<ChatMessage[]>([])
  const status = ref<ServerStatus | null>(null)
  const isThinking = ref(false)
  const isConnected = ref(false)
  const isSpeaking = ref(false)
  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let idCounter = 0

  const config = useRuntimeConfig()
  const wsUrl = computed(() =>
    (config.public.apiBase as string).replace(/^http/, 'ws') + '/ws/chat'
  )

  const connect = () => {
    if (ws) ws.close()
    ws = new WebSocket(wsUrl.value)

    ws.onopen = () => {
      isConnected.value = true
      if (reconnectTimer) clearTimeout(reconnectTimer)
    }

    ws.onmessage = (event: MessageEvent) => {
      const data = JSON.parse(event.data as string)

      if (data.type === 'thinking') {
        isThinking.value = true
        isSpeaking.value = false
      } else if (data.type === 'speaking') {
        isSpeaking.value = data.state === 'start'
      } else if (data.type === 'response') {
        isThinking.value = false
        messages.value.push({ id: ++idCounter, role: 'user', text: data.user, fromVoice: data.fromVoice })
        messages.value.push({ id: ++idCounter, role: 'ai', text: data.text, elapsed: data.elapsed })
      } else if (data.type === 'status') {
        status.value = data as ServerStatus
      } else if (data.type === 'error') {
        isThinking.value = false
        isSpeaking.value = false
        messages.value.push({ id: ++idCounter, role: 'error', text: data.message })
      }
    }

    ws.onerror = () => {
      isConnected.value = false
    }

    ws.onclose = () => {
      isConnected.value = false
      isSpeaking.value = false
      reconnectTimer = setTimeout(connect, 3000)
    }
  }

  const sendChat = (text: string, fromVoice = false) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'chat', text, fromVoice }))
    }
  }

  const switchBackend = (backend: string) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'switch_backend', backend }))
    }
  }

  const toggleAudio = () => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'toggle_audio' }))
    }
  }

  onMounted(() => {
    if (import.meta.client) connect()
  })

  onUnmounted(() => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
  })

  return { messages, status, isThinking, isConnected, isSpeaking, sendChat, switchBackend, toggleAudio }
}
