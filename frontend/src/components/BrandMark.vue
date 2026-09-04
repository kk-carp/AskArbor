<script setup lang="ts">
defineProps<{
  size?: number;
}>();
</script>

<template>
  <svg
    class="brand-mark"
    :width="size ?? 28"
    :height="size ?? 28"
    viewBox="0 0 28 28"
    fill="none"
    aria-hidden="true"
  >
    <rect width="28" height="28" rx="8" fill="#EFF6FF" />
    <path d="M7 8.2C7 7.5 7.55 7 8.25 7H14v13.2H8.7C7.7 20.2 7 19.45 7 18.4V8.2Z" fill="#2563EB" />
    <path d="M21 8.2C21 7.5 20.45 7 19.75 7H14v13.2h5.3c1 0 1.7-.75 1.7-1.8V8.2Z" fill="#93C5FD" />
  </svg>
</template>
