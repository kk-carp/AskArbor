<script setup lang="ts">
import AskMetaBanner from "@/components/qa/AskMetaBanner.vue";
import SourceList from "@/components/qa/SourceList.vue";
import type { MessageAskMeta, MessageItem } from "@/types";

defineProps<{
  messages: MessageItem[];
  metaOf: (messageId: string) => MessageAskMeta | null;
}>();
</script>

<template>
  <div class="message-pane">
    <el-empty v-if="!messages.length" description="当前为新会话，首次提问后会生成会话记录" />
    <div v-for="item in messages" :key="item.id" class="bubble" :class="item.role">
      <div class="role">{{ item.role === "user" ? "我" : "助手" }}</div>
      <div class="content">{{ item.content }}</div>
      <template v-if="item.role === 'assistant'">
        <AskMetaBanner :meta="metaOf(item.id)" />
        <SourceList v-if="metaOf(item.id)" :sources="metaOf(item.id)?.sources || []" />
      </template>
    </div>
  </div>
</template>

<style scoped>
.message-pane {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.bubble {
  max-width: 86%;
  padding: 12px 14px;
  border-radius: 10px;
  background: #fff;
  border: 1px solid #ebeef5;
}

.bubble.user {
  align-self: flex-end;
  background: #ecf5ff;
}

.bubble.assistant {
  align-self: flex-start;
}

.role {
  font-size: 12px;
  color: #909399;
  margin-bottom: 6px;
}

.content {
  white-space: pre-wrap;
  line-height: 1.6;
}
</style>
