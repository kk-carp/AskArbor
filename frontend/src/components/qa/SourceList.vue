<script setup lang="ts">
import { computed } from "vue";
import type { SourceItem } from "@/types";
import { spaceLabel } from "@/utils/labels";

const props = defineProps<{
  sources: SourceItem[];
}>();

const countLabel = computed(() => `参考 ${props.sources.length} 篇资料`);

function fileHref(item: SourceItem): string {
  return `/documents/${item.document_id}/file`;
}

function formatScore(score: number | null | undefined): string {
  if (typeof score !== "number" || Number.isNaN(score)) {
    return "";
  }
  return score.toFixed(4);
}
</script>

<template>
  <details v-if="sources.length" class="source-fold">
    <summary>{{ countLabel }}</summary>
    <ul>
      <li v-for="item in sources" :key="`${item.document_id}-${item.path || ''}-${item.score ?? ''}`">
        <a class="source-title" :href="fileHref(item)" target="_blank" rel="noopener noreferrer">
          {{ item.title }}
        </a>
        <span class="source-space">{{ spaceLabel(item.space_id) }}</span>
        <span v-if="formatScore(item.score)" class="source-score">相似度 {{ formatScore(item.score) }}</span>
        <span v-if="item.path" class="source-path">{{ item.path }}</span>
        <p v-if="item.snippet" class="source-snippet">{{ item.snippet }}</p>
      </li>
    </ul>
  </details>
</template>

<style scoped>
.source-fold {
  margin-top: 12px;
  font-family: var(--font-ui);
  font-size: 13px;
  color: var(--color-muted);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  background: var(--color-page);
  padding: 0;
}

.source-fold summary {
  cursor: pointer;
  padding: 8px 12px;
  font-weight: 600;
  color: var(--color-ink);
  list-style: none;
}

.source-fold summary::-webkit-details-marker {
  display: none;
}

.source-fold summary::after {
  content: "";
  float: right;
  margin-top: 7px;
  border: 4px solid transparent;
  border-top-color: var(--color-muted);
}

.source-fold[open] summary::after {
  margin-top: 3px;
  border-top-color: transparent;
  border-bottom-color: var(--color-muted);
}

ul {
  margin: 0;
  padding: 0 12px 10px;
  list-style: none;
}

li {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: baseline;
  padding: 8px 0;
  border-top: 1px solid var(--color-line);
}

.source-title {
  color: var(--color-primary);
  font-weight: 600;
  text-decoration: none;
}

.source-title:hover {
  text-decoration: underline;
}

.source-space {
  color: var(--color-primary);
  font-size: 12px;
}

.source-score {
  font-size: 12px;
  font-variant-numeric: tabular-nums;
  color: var(--color-ink);
  background: color-mix(in srgb, var(--color-primary) 12%, transparent);
  border-radius: 4px;
  padding: 1px 6px;
}

.source-path {
  width: 100%;
  font-size: 12px;
}

.source-snippet {
  width: 100%;
  margin: 2px 0 0;
  font-size: 12px;
  line-height: 1.55;
  color: var(--color-ink);
  white-space: normal;
}
</style>
