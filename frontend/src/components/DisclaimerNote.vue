<script setup lang="ts">
const text = "答案由知识库生成，可能不准确。请勿把内部资料转发到无权查看的渠道。";
</script>

<template>
  <p class="disclaimer">{{ text }}</p>
</template>

<style scoped>
.disclaimer {
  margin: 0;
  font-size: 12px;
  line-height: 1.6;
  color: var(--color-muted);
}
</style>
