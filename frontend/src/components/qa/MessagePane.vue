<script setup lang="ts">
import { computed } from "vue";
import AskMetaBanner from "@/components/qa/AskMetaBanner.vue";
import SourceList from "@/components/qa/SourceList.vue";
import BrandMark from "@/components/BrandMark.vue";
import type { MessageAskMeta, MessageItem } from "@/types";
import { renderMarkdown } from "@/utils/markdown";

const props = defineProps<{
  messages: MessageItem[];
  metaOf: (messageId: string) => MessageAskMeta | null;
  asking?: boolean;
}>();

function assistantHtml(content: string): string {
  return renderMarkdown(content);
}

const showEmpty = computed(() => !props.messages.length && !props.asking);
</script>

<template>
  <div class="message-pane">
    <div v-if="showEmpty" class="empty-state">
      <BrandMark :size="44" />
      <h2>向知识库提问</h2>
      <p>答案只依据已入库文档</p>
    </div>
    <div v-for="item in messages" :key="item.id" class="turn" :class="item.role">
      <div v-if="item.role === 'user'" class="user-row">
        <div class="user-bubble">{{ item.content }}</div>
      </div>
      <div v-else class="assistant-row">
        <div class="assistant-label">助手</div>
        <div class="md-body" v-html="assistantHtml(item.content)" />
        <AskMetaBanner :meta="metaOf(item.id)" />
        <SourceList v-if="metaOf(item.id)" :sources="metaOf(item.id)?.sources || []" />
      </div>
    </div>
    <div v-if="asking" class="turn assistant">
      <div class="assistant-row">
        <div class="assistant-label">助手</div>
        <div class="typing-dots" aria-label="正在作答">
          <span /><span /><span />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.message-pane {
  width: min(760px, 100%);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 22px;
  padding: 28px 8px 12px;
}

.empty-state {
  margin: 12vh auto 0;
  max-width: 420px;
  text-align: center;
  color: var(--color-muted);
}

.empty-state h2 {
  margin: 16px 0 8px;
  font-family: var(--font-read);
  font-size: 22px;
  font-weight: 700;
  color: var(--color-ink);
}

.empty-state p {
  margin: 0;
  line-height: 1.7;
  font-size: 14px;
}

.user-row {
  display: flex;
  justify-content: flex-end;
}

.user-bubble {
  max-width: 78%;
  padding: 10px 14px;
  background: var(--color-user-bubble);
  border: 1px solid #dbeafe;
  border-radius: 16px 16px 4px 16px;
  line-height: 1.65;
  white-space: pre-wrap;
  color: var(--color-ink);
}

.assistant-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-muted);
  margin-bottom: 8px;
}
</style>
