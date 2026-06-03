<script setup lang="ts">
import type { RestreamMessage } from '~/composables/useVAISocket'

const props = defineProps<{
  messages: RestreamMessage[]
  isConnected: boolean
  restreamToLlm: boolean
  ownerNames: string   // comma-separated, for highlighting owner messages
}>()

const emit = defineEmits<{
  close: []
  setRestreamToLlm: [enabled: boolean]
}>()

const PLATFORM: Record<string, { label: string; color: string; bg: string }> = {
  youtube:   { label: 'YT', color: 'text-white',    bg: 'bg-red-600' },
  twitch:    { label: 'TW', color: 'text-white',    bg: 'bg-purple-600' },
  facebook:  { label: 'FB', color: 'text-white',    bg: 'bg-blue-600' },
  tiktok:    { label: 'TK', color: 'text-zinc-900', bg: 'bg-zinc-100' },
  instagram: { label: 'IG', color: 'text-white',    bg: 'bg-pink-600' },
  twitter:   { label: 'X',  color: 'text-white',    bg: 'bg-zinc-800' },
}

const platform = (type?: string) => {
  const key = (type ?? '').toLowerCase()
  return PLATFORM[key] ?? { label: (type ?? '?').slice(0, 2).toUpperCase(), color: 'text-white', bg: 'bg-zinc-600' }
}

const ownerSet = computed(() =>
  new Set(props.ownerNames.split(',').map(n => n.trim().toLowerCase()).filter(Boolean))
)

const isOwner = (name?: string) =>
  !!name && ownerSet.value.has(name.toLowerCase())

const chatContainer = ref<HTMLElement | null>(null)
watch(() => props.messages.length, async () => {
  await nextTick()
  chatContainer.value?.scrollTo({ top: chatContainer.value.scrollHeight, behavior: 'smooth' })
})
</script>

<template>
  <!-- Backdrop -->
  <div class="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm" @click="emit('close')" />

  <!-- Panel -->
  <aside
    class="fixed left-0 top-0 bottom-0 z-50 w-72 bg-zinc-900 border-r border-zinc-800 flex flex-col shadow-2xl"
    @click.stop
  >
    <!-- Header -->
    <div class="flex items-center justify-between px-4 h-12 border-b border-zinc-800 flex-shrink-0">
      <div class="flex items-center gap-2">
        <span
          class="w-2 h-2 rounded-full flex-shrink-0"
          :class="isConnected ? 'bg-rose-400 animate-pulse' : 'bg-zinc-600'"
        />
        <span class="font-semibold text-sm text-zinc-100">Restream Chat</span>
        <span v-if="messages.length" class="text-xs text-zinc-500 font-mono">{{ messages.length }}</span>
      </div>
      <button
        class="w-7 h-7 flex items-center justify-center rounded-lg text-zinc-400 hover:text-zinc-100 hover:bg-zinc-800 transition-colors"
        @click="emit('close')"
      >✕</button>
    </div>

    <!-- LLM toggle bar -->
    <div class="px-3 py-2 border-b border-zinc-800 flex-shrink-0 bg-zinc-900/80">
      <div class="flex items-center justify-between">
        <div class="flex flex-col">
          <span class="text-xs font-medium text-zinc-300">🤖 LLM อ่าน chat</span>
          <span class="text-[10px] text-zinc-600 mt-0.5">
            <span class="text-indigo-400">เจ้าของ</span> &gt; viewer
          </span>
        </div>
        <!-- Toggle switch -->
        <button
          class="relative w-10 h-5 rounded-full transition-colors duration-200 flex-shrink-0"
          :class="restreamToLlm ? 'bg-indigo-600' : 'bg-zinc-700'"
          :title="restreamToLlm ? 'ปิด LLM อ่าน chat' : 'เปิด LLM อ่าน chat'"
          @click="emit('setRestreamToLlm', !restreamToLlm)"
        >
          <span
            class="absolute top-0.5 w-4 h-4 bg-white rounded-full shadow transition-transform duration-200"
            :class="restreamToLlm ? 'translate-x-5' : 'translate-x-0.5'"
          />
        </button>
      </div>
      <!-- Priority legend -->
      <div v-if="restreamToLlm" class="mt-1.5 flex items-center gap-2 text-[10px] text-zinc-600">
        <span class="text-yellow-400">★</span><span>เจ้าของ (ด่วน)</span>
        <span class="ml-2 text-zinc-500">👥</span><span>viewer (รอคิว)</span>
      </div>
    </div>

    <!-- Messages -->
    <div ref="chatContainer" class="flex-1 overflow-y-auto py-1 scroll-smooth">
      <!-- Empty state -->
      <div
        v-if="messages.length === 0"
        class="flex flex-col items-center justify-center h-full gap-2 text-zinc-600 select-none text-center px-4"
      >
        <span class="text-3xl">💬</span>
        <p class="text-xs">
          {{ isConnected ? 'รอ chat จาก Restream…' : 'ยังไม่ได้เชื่อมต่อ Restream' }}
        </p>
      </div>

      <!-- Chat rows -->
      <div
        v-for="(msg, i) in messages"
        :key="msg.id ?? i"
        class="flex items-start gap-2.5 px-3 py-1.5 transition-colors"
        :class="isOwner(msg.author?.displayName) ? 'bg-indigo-950/40' : 'hover:bg-zinc-800/30'"
      >
        <!-- Avatar / platform badge -->
        <div class="flex-shrink-0 relative mt-0.5">
          <img
            v-if="msg.author?.avatar"
            :src="msg.author.avatar"
            class="w-7 h-7 rounded-full object-cover"
            :alt="msg.author.displayName"
            @error="($event.target as HTMLImageElement).style.display = 'none'"
          />
          <div
            v-else
            class="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold"
            :class="[platform(msg.author?.type).bg, platform(msg.author?.type).color]"
          >
            {{ (msg.author?.displayName ?? '?').slice(0, 1).toUpperCase() }}
          </div>
          <!-- Platform badge -->
          <span
            class="absolute -bottom-0.5 -right-0.5 w-3.5 h-3.5 rounded-sm text-[8px] font-bold flex items-center justify-center border border-zinc-900"
            :class="[platform(msg.author?.type).bg, platform(msg.author?.type).color]"
          >{{ platform(msg.author?.type).label.slice(0, 2) }}</span>
        </div>

        <!-- Content -->
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1 mb-0.5 flex-wrap">
            <!-- Owner star -->
            <span v-if="isOwner(msg.author?.displayName)" class="text-yellow-400 text-xs leading-none">★</span>
            <span class="text-xs font-semibold truncate" :class="isOwner(msg.author?.displayName) ? 'text-indigo-300' : 'text-zinc-200'">
              {{ msg.author?.displayName ?? 'Unknown' }}
            </span>
            <span
              class="flex-shrink-0 text-[9px] font-bold px-1 rounded leading-tight"
              :class="[platform(msg.author?.type).bg, platform(msg.author?.type).color]"
            >{{ platform(msg.author?.type).label }}</span>
          </div>
          <p class="text-xs text-zinc-400 break-words leading-relaxed">{{ msg.text }}</p>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <div class="px-3 py-2 border-t border-zinc-800 flex-shrink-0">
      <p class="text-[10px] text-zinc-600 text-center select-none">
        ตั้ง <code class="text-zinc-500">RESTREAM_OWNER_NAMES</code> ใน .env
      </p>
    </div>
  </aside>
</template>
