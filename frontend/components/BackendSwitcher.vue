<script setup lang="ts">
import type { ServerStatus } from '~/composables/useVAISocket'

const props = defineProps<{
  status: ServerStatus | null
  isConnected: boolean
}>()

const emit = defineEmits<{
  switch: [backend: string]
}>()
</script>

<template>
  <div class="flex items-center gap-2">
    <!-- Connection dot -->
    <span
      class="w-2 h-2 rounded-full flex-shrink-0"
      :class="isConnected ? 'bg-emerald-400' : 'bg-red-500 animate-pulse'"
      :title="isConnected ? 'Connected' : 'Disconnected'"
    />

    <template v-if="status">
      <!-- Backend toggle -->
      <div class="flex rounded-lg overflow-hidden border border-zinc-600 text-xs">
        <button
          class="px-2.5 py-1 transition-colors"
          :class="status.backend === 'gemini'
            ? 'bg-indigo-600 text-white'
            : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'"
          @click="emit('switch', 'gemini')"
        >
          Gemini
        </button>
        <button
          class="px-2.5 py-1 transition-colors"
          :class="status.backend === 'lmstudio'
            ? 'bg-indigo-600 text-white'
            : 'bg-zinc-800 text-zinc-400 hover:bg-zinc-700'"
          @click="emit('switch', 'lmstudio')"
        >
          LM Studio
          <span
            v-if="status.backend !== 'lmstudio'"
            class="ml-1"
            :class="status.lmstudio_healthy ? 'text-emerald-400' : 'text-red-400'"
          >{{ status.lmstudio_healthy ? '●' : '○' }}</span>
        </button>
      </div>

      <!-- Active model label -->
      <span class="text-zinc-500 text-xs hidden sm:inline">
        {{
          status.backend === 'gemini'
            ? status.gemini_model
            : status.lmstudio_model
        }}
      </span>
    </template>

    <span v-else class="text-zinc-500 text-xs">Connecting...</span>
  </div>
</template>
