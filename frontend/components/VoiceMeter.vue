<script setup lang="ts">
const props = defineProps<{
  level: number   // 0–100 from analyser
  active: boolean
}>()

// Bell-curve multipliers so center bar is tallest
const MULTIPLIERS = [0.35, 0.65, 1.0, 0.65, 0.35]
const MIN_H = 3
const MAX_H = 20

const barHeights = computed(() =>
  MULTIPLIERS.map(m =>
    props.active
      ? Math.max(MIN_H, Math.min(MAX_H, Math.round(props.level * m * 0.22)))
      : MIN_H
  )
)
</script>

<template>
  <div class="flex items-end gap-0.5 flex-shrink-0" style="height: 20px; width: 28px">
    <div
      v-for="(h, i) in barHeights"
      :key="i"
      class="w-1 rounded-full"
      :class="active ? 'bg-rose-400' : 'bg-zinc-600'"
      :style="{ height: h + 'px', transition: 'height 55ms ease' }"
    />
  </div>
</template>
