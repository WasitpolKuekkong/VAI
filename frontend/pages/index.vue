<script setup lang="ts">
const { messages, status, isThinking, isConnected, isSpeaking, sendChat, switchBackend, toggleAudio } = useVAISocket()

const inputText = ref('')
const chatContainer = ref<HTMLElement | null>(null)

// Voice: transcript from STT gets sent directly to chat
const onVoiceTranscript = (text: string) => {
  if (!isThinking.value && isConnected.value) {
    sendChat(text, true)
  }
}

const {
  isListening, isVAD, isPTT, transcript,
  audioLevel, isSupported, hasPermission,
  startPTT, stopPTT, toggleVAD,
} = useVoiceInput(onVoiceTranscript)

// --- Input handling ---
const handleSend = () => {
  const text = inputText.value.trim()
  if (!text || isThinking.value || !isConnected.value) return
  sendChat(text)
  inputText.value = ''
  resetHeight()
}

const handleKeydown = (e: KeyboardEvent) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    handleSend()
  }
}

const textareaRef = ref<HTMLTextAreaElement | null>(null)

const autoResize = () => {
  const el = textareaRef.value
  if (!el) return
  el.style.height = 'auto'
  el.style.height = Math.min(el.scrollHeight, 112) + 'px'
}

const resetHeight = () => {
  if (textareaRef.value) textareaRef.value.style.height = 'auto'
}

// Auto-scroll
watch([messages, isThinking], async () => {
  await nextTick()
  chatContainer.value?.scrollTo({ top: chatContainer.value.scrollHeight, behavior: 'smooth' })
}, { deep: true })
</script>

<template>
  <div class="flex flex-col h-screen bg-zinc-950 text-zinc-100">

    <!-- ─── Header ─── -->
    <header class="flex items-center justify-between px-4 h-12 bg-zinc-900 border-b border-zinc-800 flex-shrink-0">

      <!-- Left: logo + connection -->
      <div class="flex items-center gap-2.5">
        <span
          class="w-2 h-2 rounded-full transition-colors duration-500 flex-shrink-0"
          :class="isConnected ? 'bg-indigo-400' : 'bg-zinc-600 animate-pulse'"
        />
        <span class="font-bold tracking-wide text-sm">VAI</span>
        <span class="text-zinc-600 text-xs hidden sm:block">AI VTuber</span>
      </div>

      <!-- Right: speaking + mute + backend -->
      <div class="flex items-center gap-3">

        <!-- AI speaking waveform -->
        <transition name="fade">
          <div v-if="isSpeaking" class="flex items-center gap-1.5 text-emerald-400">
            <div class="flex items-end gap-0.5" style="height:14px">
              <span
                v-for="i in 4" :key="i"
                class="block w-0.5 rounded-full bg-emerald-400"
                :style="{
                  height: '100%',
                  animation: 'wave 0.7s ease-in-out infinite',
                  animationDelay: `${i * 0.12}s`,
                }"
              />
            </div>
            <span class="text-xs font-medium">Speaking</span>
          </div>
        </transition>

        <!-- Audio mute toggle -->
        <button
          v-if="status"
          class="w-7 h-7 flex items-center justify-center rounded-lg transition-colors text-sm"
          :class="status.audio_enabled
            ? 'text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
            : 'text-zinc-600 hover:text-zinc-400 hover:bg-zinc-800'"
          :title="status.audio_enabled ? 'Mute AI voice' : 'Unmute AI voice'"
          @click="toggleAudio"
        >
          {{ status.audio_enabled ? '🔊' : '🔇' }}
        </button>

        <BackendSwitcher :status :is-connected="isConnected" @switch="switchBackend" />
      </div>
    </header>

    <!-- ─── Messages ─── -->
    <main
      ref="chatContainer"
      class="flex-1 overflow-y-auto px-4 py-4 space-y-1 scroll-smooth"
    >
      <!-- Empty state -->
      <div
        v-if="messages.length === 0 && !isThinking"
        class="flex flex-col items-center justify-center h-full gap-3 text-zinc-600 select-none"
      >
        <div class="w-14 h-14 rounded-2xl bg-zinc-900 flex items-center justify-center text-3xl shadow-inner">
          🎙️
        </div>
        <p class="text-sm">พิมพ์หรือพูดเพื่อเริ่มคุยกับ VAI</p>
        <p v-if="isSupported && !hasPermission" class="text-xs text-zinc-700">
          กด 🎤 เพื่ออนุญาตไมโครโฟน
        </p>
      </div>

      <!-- Chat bubbles -->
      <ChatBubble v-for="msg in messages" :key="msg.id" :message="msg" />

      <!-- Thinking dots (hidden while speaking to avoid double indicator) -->
      <div v-if="isThinking && !isSpeaking" class="flex justify-start mb-1 pl-1">
        <div class="flex items-center gap-2 bg-zinc-800/80 rounded-2xl rounded-tl-sm px-4 py-2.5">
          <span class="text-zinc-500 text-xs">VAI</span>
          <div class="flex gap-1">
            <span
              v-for="i in 3" :key="i"
              class="w-1.5 h-1.5 rounded-full bg-zinc-500 animate-bounce"
              :style="{ animationDelay: `${(i - 1) * 150}ms` }"
            />
          </div>
        </div>
      </div>
    </main>

    <!-- ─── STT Preview ─── -->
    <transition name="slide-up">
      <div
        v-if="transcript"
        class="px-4 py-2 bg-zinc-900/80 border-t border-zinc-800 flex-shrink-0 backdrop-blur"
      >
        <p class="text-sm text-zinc-400 italic truncate">
          <span class="inline-block w-1.5 h-1.5 rounded-full bg-rose-400 mr-2 animate-pulse align-middle" />
          {{ transcript }}
        </p>
      </div>
    </transition>

    <!-- ─── Input Bar ─── -->
    <footer class="px-3 py-2.5 bg-zinc-900 border-t border-zinc-800 flex-shrink-0">
      <div class="flex items-end gap-2">

        <!-- Voice zone (mic + level meter) -->
        <div v-if="isSupported" class="flex items-end gap-1.5 flex-shrink-0 pb-0.5">
          <!-- VAD toggle -->
          <button
            class="w-8 h-8 rounded-xl flex items-center justify-center text-sm transition-all duration-150 flex-shrink-0"
            :class="isVAD
              ? 'bg-rose-600 text-white shadow-lg shadow-rose-900/40 scale-95'
              : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200'"
            :title="isVAD ? 'Voice activation ON — click to disable' : 'Enable voice activation'"
            @click="toggleVAD"
          >
            🎤
          </button>

          <!-- Level meter (only when voice is active) -->
          <VoiceMeter
            :level="audioLevel"
            :active="isListening || isVAD"
          />
        </div>

        <!-- Text input -->
        <textarea
          ref="textareaRef"
          v-model="inputText"
          rows="1"
          placeholder="พิมพ์ข้อความ…"
          class="flex-1 resize-none bg-zinc-800 text-zinc-100 placeholder-zinc-600 rounded-xl px-3.5 py-2 text-sm outline-none focus:ring-1 focus:ring-indigo-500/50 overflow-y-auto transition-all"
          style="min-height: 36px; max-height: 112px"
          :disabled="!isConnected || isThinking"
          @keydown="handleKeydown"
          @input="autoResize"
        />

        <!-- PTT button (hold to talk) -->
        <button
          v-if="isSupported"
          class="w-8 h-8 rounded-xl flex items-center justify-center text-xs transition-all duration-100 flex-shrink-0 pb-0.5 select-none"
          :class="isPTT
            ? 'bg-rose-600 text-white scale-95 shadow-lg shadow-rose-900/40'
            : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200'"
          :disabled="!isConnected || isThinking"
          title="Hold to talk"
          @mousedown.prevent="startPTT"
          @mouseup.prevent="stopPTT"
          @mouseleave="() => { if (isPTT) stopPTT() }"
          @touchstart.prevent="startPTT"
          @touchend.prevent="stopPTT"
        >
          ⏺
        </button>

        <!-- Send button -->
        <button
          class="w-8 h-8 rounded-xl flex items-center justify-center font-bold text-sm transition-all duration-150 flex-shrink-0 pb-0.5"
          :class="isConnected && !isThinking && inputText.trim()
            ? 'bg-indigo-600 hover:bg-indigo-500 text-white shadow-lg shadow-indigo-900/30'
            : 'bg-zinc-800 text-zinc-600 cursor-not-allowed'"
          :disabled="!isConnected || isThinking || !inputText.trim()"
          @click="handleSend"
        >
          ↑
        </button>

      </div>

      <!-- Keyboard hints -->
      <p class="text-zinc-700 text-xs mt-1.5 px-1 select-none">
        <span v-if="isSupported">🎤 VAD &nbsp;|&nbsp; ⏺ PTT &nbsp;|&nbsp;</span>
        Enter ส่ง &nbsp;·&nbsp; Shift+Enter ขึ้นบรรทัด
      </p>
    </footer>

  </div>
</template>

<style scoped>
@keyframes wave {
  0%, 100% { transform: scaleY(0.25); }
  50%       { transform: scaleY(1); }
}

.fade-enter-active, .fade-leave-active { transition: opacity 0.25s ease; }
.fade-enter-from, .fade-leave-to        { opacity: 0; }

.slide-up-enter-active, .slide-up-leave-active { transition: all 0.2s ease; }
.slide-up-enter-from, .slide-up-leave-to       { opacity: 0; transform: translateY(6px); }
</style>
