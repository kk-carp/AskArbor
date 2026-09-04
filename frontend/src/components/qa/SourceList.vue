<script setup lang="ts">
import type { SourceItem } from "@/types";
import { spaceLabel } from "@/utils/labels";

defineProps<{
  sources: SourceItem[];
}>();
</script>

<template>
  <div class="source-block">
    <div class="source-title">来源</div>
    <p v-if="!sources.length" class="empty">无来源</p>
    <ul v-else>
      <li v-for="item in sources" :key="item.document_id">
        <strong>{{ item.title }}</strong>
        <span>（{{ spaceLabel(item.space_id) }}）</span>
        <span v-if="item.path"> · {{ item.path }}</span>
      </li>
    </ul>
  </div>
</template>

<style scoped>
.source-block {
  margin-top: 8px;
  font-size: 13px;
  color: #606266;
}

.source-title {
  font-weight: 600;
  margin-bottom: 4px;
}

.empty,
ul {
  margin: 0;
  padding: 0;
}

ul {
  padding-left: 18px;
}
</style>
