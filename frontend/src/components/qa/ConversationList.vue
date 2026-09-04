<script setup lang="ts">
import type { ConversationItem } from "@/types";
import { formatDateTime, shortId } from "@/utils/labels";

defineProps<{
  items: ConversationItem[];
  currentId: string | null;
  loading: boolean;
}>();

const emit = defineEmits<{
  select: [id: string | null];
  create: [];
}>();
</script>

<template>
  <div class="conversation-list">
    <el-button type="primary" class="new-btn" @click="emit('create')">开启新会话</el-button>
    <el-skeleton :loading="loading" animated :rows="6">
      <el-empty v-if="!items.length" description="暂无历史会话" :image-size="64" />
      <el-scrollbar v-else height="100%">
        <button
          v-for="item in items"
          :key="item.id"
          type="button"
          class="conv-item"
          :class="{ active: item.id === currentId }"
          @click="emit('select', item.id)"
        >
          <div class="conv-id">{{ shortId(item.id) }}</div>
          <div class="conv-meta">{{ item.message_count }} 条 · {{ formatDateTime(item.updated_at) }}</div>
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
}

.new-btn {
  width: 100%;
}

.conv-item {
  width: 100%;
  text-align: left;
  border: 1px solid #ebeef5;
  background: #fff;
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 8px;
  cursor: pointer;
}

.conv-item.active {
  border-color: #409eff;
  background: #ecf5ff;
}

.conv-id {
  font-weight: 600;
}

.conv-meta {
  color: #909399;
  font-size: 12px;
  margin-top: 4px;
}
</style>
