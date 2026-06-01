<script setup lang="ts">
import type { ChatMessage } from '~/composables/useVAISocket'

defineProps<{ message: ChatMessage }>()
</script>

<template>
  <div
    class="flex w-full mb-3"
    :class="message.role === 'user' ? 'justify-end' : 'justify-start'"
  >
    <!-- AI / Error bubble -->
    <div
      v-if="message.role !== 'user'"
      class="max-w-[75%] rounded-2xl rounded-tl-sm px-4 py-2.5 text-sm leading-relaxed"
      :class="message.role === 'error'
        ? 'bg-red-900/60 text-red-200 border border-red-700'
        : 'bg-zinc-700 text-zinc-100'"
    >
      <span class="block font-semibold text-xs mb-1 opacity-60">
        {{ message.role === 'error' ? 'Error' : 'VAI' }}
        <span v-if="message.elapsed" class="ml-1 font-normal">{{ message.elapsed }}s</span>
      </span>
      <p class="whitespace-pre-wrap">{{ message.text }}</p>
    </div>

    <!-- User bubble -->
    <div
      v-else
      class="max-w-[75%] rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm leading-relaxed bg-indigo-600 text-white"
    >
      <span class="block font-semibold text-xs mb-1 opacity-70">You</span>
      <p class="whitespace-pre-wrap">{{ message.text }}</p>
    </div>
  </div>
</template>
