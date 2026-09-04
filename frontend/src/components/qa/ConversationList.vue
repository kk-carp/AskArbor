<script setup lang="ts">
import type { ConversationItem } from "@/types";
import { formatDateTime } from "@/utils/labels";

defineProps<{
  items: ConversationItem[];
  currentId: string | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  select: [id: string | null];
  create: [];
}>();

function conversationTitle(item: ConversationItem): string {
  const text = item.preview?.trim();
  return text || "新会话";
}
</script>

<template>
  <div class="conversation-list">
    <el-button type="primary" class="new-btn" @click="emit('create')">新对话</el-button>
    <el-skeleton :loading="loading" animated :rows="6">
      <el-empty v-if="!items.length" description="还没有历史对话" :image-size="56" />
      <el-scrollbar v-else height="100%">
        <button
          v-for="item in items"
          :key="item.id"
          type="button"
          class="conv-item"
          :class="{ active: item.id === currentId }"
          :title="conversationTitle(item)"
          @click="emit('select', item.id)"
        >
          <div class="conv-title">{{ conversationTitle(item) }}</div>
          <div class="conv-meta">{{ item.message_count }} 条，{{ formatDateTime(item.updated_at) }}</div>
        </button>
      </el-scrollbar>
    </el-skeleton>
  </div>
</template>

<style scoped>
.conversation-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  height: 100%;
  padding: 16px 12px 12px;
}

.conversation-list :deep(.el-skeleton),
.conversation-list :deep(.el-scrollbar) {
  flex: 1;
  min-height: 0;
}

.new-btn {
  width: 100%;
  height: 38px;
  border-radius: 10px;
}

.conv-item {
  width: 100%;
  text-align: left;
  border: 1px solid transparent;
  background: transparent;
  border-radius: 10px;
  padding: 10px 12px;
  margin-bottom: 4px;
  cursor: pointer;
  color: var(--color-ink);
}

.conv-item:hover {
  background: var(--color-page);
}

.conv-item.active {
  background: var(--color-primary-soft);
  border-color: transparent;
}

.conv-title {
  font-weight: 600;
  font-size: 13px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-meta {
  color: var(--color-muted);
  font-size: 12px;
  margin-top: 4px;
}
</style>
