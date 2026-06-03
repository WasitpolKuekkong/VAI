<script setup lang="ts">
import type { ServerStatus, AudioDevice } from '~/composables/useVAISocket'

const props = defineProps<{
  status: ServerStatus | null
  isConnected: boolean
  vtsConnected: boolean
  vtsStatusMessage: string
  restreamConnected: boolean
  restreamStatusMessage: string
  selectedMicId: string
}>()

const emit = defineEmits<{
  changeModel: [backend: string, model: string]
  setTTS: [pitch: number, rate: number]
  setAudioOutput: [deviceId: number | null]
  connectVTS: []
  disconnectVTS: []
  connectRestream: []
  disconnectRestream: []
  setMicDevice: [deviceId: string]
  close: []
}>()

// ── Model selectors ──────────────────────────────────────────────────────────
const GEMINI_MODELS = [
  'gemini-2.5-flash',
  'gemini-2.5-pro',
  'gemini-2.0-flash',
  'gemini-1.5-pro',
  'gemini-1.5-flash',
]

const selectedGeminiModel = ref(props.status?.gemini_model ?? 'gemini-2.5-flash')
const selectedLMModel = ref(props.status?.lmstudio_model ?? '')

watch(() => props.status?.gemini_model, (v) => { if (v) selectedGeminiModel.value = v })
watch(() => props.status?.lmstudio_model, (v) => { if (v) selectedLMModel.value = v })

const applyGeminiModel = () => emit('changeModel', 'gemini', selectedGeminiModel.value)
const applyLMModel = () => {
  if (selectedLMModel.value.trim()) emit('changeModel', 'lmstudio', selectedLMModel.value.trim())
}

// ── TTS controls ─────────────────────────────────────────────────────────────
const ttsPitch = ref(props.status?.tts_pitch ?? 0)
const ttsRate = ref(props.status?.tts_rate ?? 20)

watch(() => props.status?.tts_pitch, (v) => { if (v !== undefined) ttsPitch.value = v })
watch(() => props.status?.tts_rate, (v) => { if (v !== undefined) ttsRate.value = v })

const applyTTS = () => emit('setTTS', ttsPitch.value, ttsRate.value)

// ── Audio devices ─────────────────────────────────────────────────────────────
const outputDevices = ref<AudioDevice[]>([])
const inputDevices = ref<{ deviceId: string; label: string }[]>([])
const selectedOutputId = ref<number | null>(props.status?.audio_output_device ?? null)
const selectedMicIdLocal = ref(props.selectedMicId)

watch(() => props.status?.audio_output_device, (v) => { selectedOutputId.value = v ?? null })
watch(() => props.selectedMicId, (v) => { selectedMicIdLocal.value = v })

const loadingDevices = ref(false)

const loadAudioDevices = async () => {
  loadingDevices.value = true
  try {
    const apiBase = useRuntimeConfig().public.apiBase as string
    const res = await fetch(`${apiBase}/api/audio-devices`)
    const data = await res.json()
    if (data.ok) {
      outputDevices.value = (data.devices as AudioDevice[]).filter(d => d.max_output_channels > 0)
    }

    // Browser input devices (requires permission — may show generic labels before grant)
    const allDevices = await navigator.mediaDevices.enumerateDevices()
    inputDevices.value = allDevices
      .filter(d => d.kind === 'audioinput')
      .map(d => ({ deviceId: d.deviceId, label: d.label || `Microphone ${d.deviceId.slice(0, 6)}` }))
  } catch {}
  loadingDevices.value = false
}

const applyOutputDevice = () => emit('setAudioOutput', selectedOutputId.value)
const applyMicDevice = () => emit('setMicDevice', selectedMicIdLocal.value)

onMounted(loadAudioDevices)
</script>

<template>
  <!-- Backdrop -->
  <div
    class="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm"
    @click="emit('close')"
  />

  <!-- Panel -->
  <aside
    class="fixed right-0 top-0 bottom-0 z-50 w-80 bg-zinc-900 border-l border-zinc-800 flex flex-col overflow-y-auto shadow-2xl"
    @click.stop
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-4 h-12 border-b border-zinc-800 flex-shrink-0">
      <span class="font-semibold text-sm text-zinc-100">Settings</span>
      <button
        class="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
        @click="emit('close')"
      >✕</button>
    </div>

    <div class="flex-1 px-4 py-4 space-y-6 text-sm">

      <!-- ── LLM Models ────────────────────────────────────────── -->
      <section>
        <h3 class="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">LLM Models</h3>

        <!-- Gemini model -->
        <div class="mb-3">
          <label class="block text-zinc-400 mb-1.5">Gemini model</label>
          <div class="flex gap-2">
            <select
              v-model="selectedGeminiModel"
              class="flex-1 bg-zinc-800 text-zinc-100 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-indigo-500/50 border border-zinc-700"
            >
              <option v-for="m in GEMINI_MODELS" :key="m" :value="m">{{ m }}</option>
            </select>
            <button
              class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors"
              @click="applyGeminiModel"
            >Apply</button>
          </div>
          <p v-if="status?.backend === 'gemini'" class="text-xs text-indigo-400 mt-1">Active backend</p>
        </div>

        <!-- LM Studio model -->
        <div>
          <label class="block text-zinc-400 mb-1.5">LM Studio model</label>
          <div class="flex gap-2">
            <input
              v-model="selectedLMModel"
              type="text"
              placeholder="e.g. qwen/qwen3-8b"
              class="flex-1 bg-zinc-800 text-zinc-100 placeholder-zinc-600 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-indigo-500/50 border border-zinc-700"
              @keydown.enter="applyLMModel"
            />
            <button
              class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors"
              @click="applyLMModel"
            >Apply</button>
          </div>
          <p
            v-if="status"
            class="text-xs mt-1"
            :class="status.lmstudio_healthy ? 'text-emerald-400' : 'text-red-400'"
          >
            {{ status.lmstudio_healthy ? '● Connected' : '○ Unreachable' }} — {{ status.lmstudio_url }}
          </p>
          <p v-if="status?.backend === 'lmstudio'" class="text-xs text-indigo-400 mt-0.5">Active backend</p>
        </div>
      </section>

      <!-- ── TTS Voice ─────────────────────────────────────────── -->
      <section>
        <h3 class="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">TTS Voice</h3>

        <!-- Pitch -->
        <div class="mb-4">
          <div class="flex items-center justify-between mb-1.5">
            <label class="text-zinc-400">Pitch</label>
            <span class="text-xs font-mono text-indigo-400">
              {{ ttsPitch > 0 ? '+' : '' }}{{ ttsPitch }} st
            </span>
          </div>
          <input
            v-model.number="ttsPitch"
            type="range" min="-12" max="12" step="1"
            class="w-full accent-indigo-500 cursor-pointer"
          />
          <div class="flex justify-between text-xs text-zinc-700 mt-0.5 select-none">
            <span>-12</span><span>0</span><span>+12</span>
          </div>
        </div>

        <!-- Rate -->
        <div class="mb-3">
          <div class="flex items-center justify-between mb-1.5">
            <label class="text-zinc-400">ความเร็ว</label>
            <span class="text-xs font-mono text-indigo-400">
              {{ ttsRate > 0 ? '+' : '' }}{{ ttsRate }}%
            </span>
          </div>
          <input
            v-model.number="ttsRate"
            type="range" min="-50" max="100" step="5"
            class="w-full accent-indigo-500 cursor-pointer"
          />
          <div class="flex justify-between text-xs text-zinc-700 mt-0.5 select-none">
            <span>-50%</span><span>0</span><span>+100%</span>
          </div>
        </div>

        <button
          class="w-full py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors"
          @click="applyTTS"
        >Apply Voice Settings</button>
      </section>

      <!-- ── Audio Devices ─────────────────────────────────────── -->
      <section>
        <h3 class="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Audio Devices</h3>

        <!-- Microphone (browser) -->
        <div class="mb-3">
          <label class="block text-zinc-400 mb-1.5">Microphone (voice input)</label>
          <div class="flex gap-2">
            <select
              v-model="selectedMicIdLocal"
              class="flex-1 bg-zinc-800 text-zinc-100 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-indigo-500/50 border border-zinc-700 truncate"
            >
              <option value="">System default</option>
              <option v-for="d in inputDevices" :key="d.deviceId" :value="d.deviceId">
                {{ d.label }}
              </option>
            </select>
            <button
              class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors"
              @click="applyMicDevice"
            >Apply</button>
          </div>
          <p class="text-xs text-zinc-600 mt-1">Affects level meter; STT uses system default mic</p>
        </div>

        <!-- Output device (Python backend) -->
        <div>
          <label class="block text-zinc-400 mb-1.5">Audio output (VAI voice)</label>
          <div v-if="loadingDevices" class="text-xs text-zinc-600">Loading devices…</div>
          <div v-else class="flex gap-2">
            <select
              v-model="selectedOutputId"
              class="flex-1 bg-zinc-800 text-zinc-100 rounded-lg px-3 py-1.5 text-sm outline-none focus:ring-1 focus:ring-indigo-500/50 border border-zinc-700 truncate"
            >
              <option :value="null">Auto-detect (VB-Cable)</option>
              <option v-for="d in outputDevices" :key="d.id" :value="d.id">
                [{{ d.id }}] {{ d.name }}
              </option>
            </select>
            <button
              class="px-3 py-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-xs font-medium transition-colors"
              @click="applyOutputDevice"
            >Apply</button>
          </div>
        </div>
      </section>

      <!-- ── Integrations ──────────────────────────────────────── -->
      <section>
        <h3 class="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3">Integrations</h3>

        <!-- VTube Studio -->
        <div class="mb-4">
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span
                class="w-2 h-2 rounded-full flex-shrink-0 transition-colors"
                :class="vtsConnected ? 'bg-emerald-400' : 'bg-zinc-600'"
              />
              <span class="text-zinc-200 font-medium">VTube Studio</span>
            </div>
            <button
              class="px-3 py-1 rounded-lg text-xs font-medium transition-colors"
              :class="vtsConnected
                ? 'bg-zinc-700 hover:bg-zinc-600 text-zinc-300'
                : 'bg-emerald-700 hover:bg-emerald-600 text-white'"
              @click="vtsConnected ? emit('disconnectVTS') : emit('connectVTS')"
            >
              {{ vtsConnected ? 'Disconnect' : 'Connect' }}
            </button>
          </div>
          <p v-if="vtsStatusMessage" class="text-xs text-zinc-500 leading-relaxed">{{ vtsStatusMessage }}</p>
          <p v-else class="text-xs text-zinc-600">ws://localhost:8001</p>
        </div>

        <!-- Restream -->
        <div>
          <div class="flex items-center justify-between mb-2">
            <div class="flex items-center gap-2">
              <span
                class="w-2 h-2 rounded-full flex-shrink-0 transition-colors"
                :class="restreamConnected ? 'bg-emerald-400' : 'bg-zinc-600'"
              />
              <span class="text-zinc-200 font-medium">Restream</span>
            </div>
            <button
              class="px-3 py-1 rounded-lg text-xs font-medium transition-colors"
              :class="restreamConnected
                ? 'bg-zinc-700 hover:bg-zinc-600 text-zinc-300'
                : 'bg-rose-700 hover:bg-rose-600 text-white'"
              @click="restreamConnected ? emit('disconnectRestream') : emit('connectRestream')"
            >
              {{ restreamConnected ? 'Disconnect' : 'Connect' }}
            </button>
          </div>
          <p v-if="restreamStatusMessage" class="text-xs text-zinc-500 leading-relaxed mb-2">
            {{ restreamStatusMessage }}
          </p>

          <!-- Redirect URI — must match Restream Developer Console -->
          <div v-if="status?.restream_redirect_uri" class="mt-1">
            <p class="text-xs text-zinc-600 mb-1">
              Register this URI in
              <a
                href="https://restream.io/settings/api"
                target="_blank"
                class="text-rose-400 hover:text-rose-300 underline"
              >Restream Developer Console</a>:
            </p>
            <div class="flex items-center gap-1.5">
              <code class="flex-1 text-[10px] text-zinc-400 bg-zinc-800 rounded px-2 py-1 font-mono truncate border border-zinc-700">
                {{ status.restream_redirect_uri }}
              </code>
              <button
                class="flex-shrink-0 px-2 py-1 bg-zinc-700 hover:bg-zinc-600 text-zinc-300 rounded text-xs transition-colors"
                title="Copy"
                @click="navigator.clipboard.writeText(status!.restream_redirect_uri)"
              >📋</button>
            </div>
          </div>
        </div>
      </section>

    </div>
  </aside>
</template>
