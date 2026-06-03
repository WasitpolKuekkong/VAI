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
  audio_output_device: number | null
  current_expression: string
  vts_connected: boolean
  restream_connected: boolean
  tts_pitch: number
  tts_rate: number
  restream_redirect_uri: string
  restream_to_llm: boolean
  restream_owner_names: string
}

export interface RestreamMessage {
  id?: string
  author: { displayName: string; type: string; avatar?: string | null }
  text: string
  timestamp?: number | string
  channelId?: string
}

export interface AudioDevice {
  id: number
  name: string
  max_input_channels: number
  max_output_channels: number
}

export const useVAISocket = () => {
  const messages = ref<ChatMessage[]>([])
  const status = ref<ServerStatus | null>(null)
  const isThinking = ref(false)
  const isConnected = ref(false)
  const isSpeaking = ref(false)
  const currentExpression = ref('neutral')
  const vtsConnected = ref(false)
  const restreamConnected = ref(false)
  const vtsStatusMessage = ref('')
  const restreamStatusMessage = ref('')
  const restreamMessages = ref<RestreamMessage[]>([])

  let ws: WebSocket | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let idCounter = 0

  const config = useRuntimeConfig()
  const wsUrl = computed(() =>
    (config.public.apiBase as string).replace(/^http/, 'ws') + '/ws/chat'
  )
  const apiBase = computed(() => config.public.apiBase as string)

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
        // User message already shown immediately in sendChat() — only push AI reply
        messages.value.push({ id: ++idCounter, role: 'ai', text: data.text, elapsed: data.elapsed })
        if (data.expression) currentExpression.value = data.expression
      } else if (data.type === 'status') {
        status.value = data as ServerStatus
        currentExpression.value = data.current_expression ?? 'neutral'
        vtsConnected.value = data.vts_connected ?? false
        restreamConnected.value = data.restream_connected ?? false
      } else if (data.type === 'vts_status') {
        vtsConnected.value = data.connected
        vtsStatusMessage.value = data.message ?? ''
      } else if (data.type === 'restream_status') {
        restreamConnected.value = data.connected
        restreamStatusMessage.value = data.message ?? ''
      } else if (data.type === 'restream_auth') {
        // Open OAuth popup — backend will broadcast restream_status when done
        restreamStatusMessage.value = data.message ?? 'Opening authorization...'
        const popup = window.open(data.url, 'restream_oauth', 'width=520,height=720,left=200,top=100')
        if (!popup) restreamStatusMessage.value = 'Popup blocked — allow popups for this page'
      } else if (data.type === 'restream_chat') {
        const msg = data.message as RestreamMessage
        restreamMessages.value.push(msg)
        if (restreamMessages.value.length > 200) {
          restreamMessages.value = restreamMessages.value.slice(-200)
        }
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

  // Show user message immediately, then send to server
  const sendChat = (text: string, fromVoice = false) => {
    if (ws?.readyState === WebSocket.OPEN) {
      messages.value.push({ id: ++idCounter, role: 'user', text, fromVoice })
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

  const changeModel = (backend: string, model: string) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'change_model', backend, model }))
    }
  }

  const setRestreamToLlm = (enabled: boolean) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'set_restream_to_llm', enabled }))
    }
  }

  const setTTS = (pitch?: number, rate?: number) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'set_tts', pitch, rate }))
    }
  }

  const setAudioOutput = (deviceId: number | null) => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'set_audio_output', device_id: deviceId }))
    }
  }

  const connectVTS = () => {
    if (ws?.readyState === WebSocket.OPEN) {
      vtsStatusMessage.value = 'Connecting...'
      ws.send(JSON.stringify({ type: 'connect_vts' }))
    }
  }

  const disconnectVTS = () => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'disconnect_vts' }))
    }
  }

  const connectRestream = () => {
    if (ws?.readyState === WebSocket.OPEN) {
      restreamStatusMessage.value = 'Connecting...'
      ws.send(JSON.stringify({ type: 'connect_restream' }))
    }
  }

  const disconnectRestream = () => {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'disconnect_restream' }))
    }
  }

  const fetchAudioDevices = async (): Promise<AudioDevice[]> => {
    try {
      const res = await fetch(`${apiBase.value}/api/audio-devices`)
      const data = await res.json()
      return data.ok ? data.devices : []
    } catch {
      return []
    }
  }

  onMounted(() => {
    if (import.meta.client) connect()
  })

  onUnmounted(() => {
    if (reconnectTimer) clearTimeout(reconnectTimer)
    ws?.close()
  })

  return {
    messages,
    status,
    isThinking,
    isConnected,
    isSpeaking,
    currentExpression,
    vtsConnected,
    restreamConnected,
    vtsStatusMessage,
    restreamStatusMessage,
    restreamMessages,
    sendChat,
    switchBackend,
    toggleAudio,
    changeModel,
    setRestreamToLlm,
    setTTS,
    setAudioOutput,
    connectVTS,
    disconnectVTS,
    connectRestream,
    disconnectRestream,
    fetchAudioDevices,
  }
}
