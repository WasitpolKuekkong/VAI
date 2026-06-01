<script setup lang="ts">
const { messages, status, isThinking, isConnected, sendChat, switchBackend } = useVAISocket()

const inputText = ref('')
const chatContainer = ref<HTMLElement | null>(null)

const handleSend = () => {
  const text = inputText.value.trim()
  if (!text || isThinking.value) return
  sendChat(text)
  inputText.value = ''
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

// Auto-scroll to bottom when new messages arrive
watch(
  [messages, isThinking],
  async () => {
    await nextTick()
    if (chatContainer.value) {
      chatContainer.value.scrollTop = chatContainer.value.scrollHeight
    }
  },
  { deep: true }
)
</script>

<template>
  <div class="flex flex-col h-screen bg-zinc-900 text-zinc-100">

    <!-- Header -->
    <header class="flex items-center justify-between px-4 py-3 bg-zinc-800 border-b border-zinc-700 flex-shrink-0">
      <div class="flex items-center gap-3">
        <span class="text-lg font-bold tracking-tight">VAI</span>
        <span class="text-zinc-500 text-sm">AI VTuber</span>
      </div>
      <BackendSwitcher
        :status="status"
        :is-connected="isConnected"
        @switch="switchBackend"
      />
    </header>

    <!-- Chat area -->
    <main
      ref="chatContainer"
      class="flex-1 overflow-y-auto px-4 py-4 space-y-1"
    >
      <!-- Empty state -->
      <div
        v-if="messages.length === 0 && !isThinking"
        class="flex flex-col items-center justify-center h-full gap-2 text-zinc-600 select-none"
      >
        <span class="text-4xl">🎙️</span>
        <p class="text-sm">พิมพ์ข้อความเพื่อเริ่มคุยกับ VAI</p>
      </div>

      <!-- Messages -->
      <ChatBubble
        v-for="msg in messages"
        :key="msg.id"
        :message="msg"
      />

      <!-- Thinking indicator -->
      <div v-if="isThinking" class="flex justify-start mb-3">
        <div class="bg-zinc-700 rounded-2xl rounded-tl-sm px-4 py-3">
          <div class="flex gap-1.5 items-center">
            <span
              v-for="i in 3"
              :key="i"
              class="w-2 h-2 rounded-full bg-zinc-400 animate-bounce"
              :style="{ animationDelay: `${(i - 1) * 150}ms` }"
            />
          </div>
        </div>
      </div>
    </main>

    <!-- Input bar -->
    <footer class="px-4 py-3 bg-zinc-800 border-t border-zinc-700 flex-shrink-0">
      <div class="flex gap-2 items-end">
        <textarea
          v-model="inputText"
          rows="1"
          placeholder="พิมพ์ข้อความ... (Enter ส่ง, Shift+Enter ขึ้นบรรทัด)"
          class="flex-1 resize-none bg-zinc-700 text-zinc-100 placeholder-zinc-500 rounded-xl px-4 py-2.5 text-sm outline-none focus:ring-2 focus:ring-indigo-500 max-h-32 overflow-y-auto"
          :disabled="!isConnected || isThinking"
          @keydown="handleKeydown"
          @input="($event.target as HTMLTextAreaElement).style.height = 'auto'; ($event.target as HTMLTextAreaElement).style.height = ($event.target as HTMLTextAreaElement).scrollHeight + 'px'"
        />
        <button
          class="px-4 py-2.5 rounded-xl text-sm font-medium transition-colors flex-shrink-0"
          :class="isConnected && !isThinking && inputText.trim()
            ? 'bg-indigo-600 hover:bg-indigo-500 text-white'
            : 'bg-zinc-700 text-zinc-500 cursor-not-allowed'"
          :disabled="!isConnected || isThinking || !inputText.trim()"
          @click="handleSend"
        >
          Send
        </button>
      </div>
    </footer>

  </div>
</template>
