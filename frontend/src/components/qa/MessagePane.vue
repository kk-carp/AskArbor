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
  imageOf?: (messageId: string) => string | null;
  asking?: boolean;
  pendingQuestion?: string;
  pendingImageUrl?: string | null;
}>();

const OCR_MARKER = "【截图文字】";

function assistantHtml(content: string): string {
  return renderMarkdown(content);
}

function splitUserContent(content: string): { prompt: string; ocrText: string | null } {
  const idx = content.indexOf(OCR_MARKER);
  if (idx < 0) {
    return { prompt: content, ocrText: null };
  }
  const prompt = content.slice(0, idx).trim();
  const ocrText = content.slice(idx + OCR_MARKER.length).trim();
  return {
    prompt: prompt || "截图提问",
    ocrText: ocrText || null,
  };
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
        <div class="user-bubble" v-for="parts in [splitUserContent(item.content)]" :key="item.id + '-u'">
          <img
            v-if="imageOf?.(item.id)"
            class="user-image"
            :src="imageOf(item.id) || ''"
            alt="上传的截图"
          />
          <div class="user-text">{{ parts.prompt }}</div>
          <details v-if="parts.ocrText" class="ocr-fold">
            <summary>{{ imageOf?.(item.id) ? "识别文字（供检索，可展开）" : "识别文字" }}</summary>
            <pre>{{ parts.ocrText }}</pre>
          </details>
        </div>
      </div>
      <div v-else class="assistant-row">
        <div class="assistant-label">助手</div>
        <div class="md-body" v-html="assistantHtml(item.content)" />
        <AskMetaBanner :meta="metaOf(item.id)" />
        <SourceList v-if="metaOf(item.id)" :sources="metaOf(item.id)?.sources || []" />
      </div>
    </div>
    <div v-if="asking" class="turn user">
      <div class="user-row">
        <div class="user-bubble pending">
          <img v-if="pendingImageUrl" class="user-image" :src="pendingImageUrl" alt="上传的截图" />
          <div class="user-text">{{ pendingQuestion || "截图提问" }}</div>
        </div>
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
  color: var(--color-ink);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.user-bubble.pending {
  opacity: 0.85;
}

.user-image {
  display: block;
  max-width: min(320px, 100%);
  max-height: 240px;
  border-radius: 10px;
  border: 1px solid var(--color-line);
  object-fit: contain;
  background: #fff;
}

.user-text {
  white-space: pre-wrap;
}

.ocr-fold {
  font-size: 12px;
  color: var(--color-muted);
}

.ocr-fold summary {
  cursor: pointer;
  user-select: none;
}

.ocr-fold pre {
  margin: 6px 0 0;
  padding: 8px;
  max-height: 160px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
  background: rgba(255, 255, 255, 0.7);
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
}

.assistant-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-muted);
  margin-bottom: 8px;
}

.typing-dots {
  display: inline-flex;
  gap: 4px;
  padding: 8px 0;
}

.typing-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-muted);
  animation: blink 1.2s infinite ease-in-out;
}

.typing-dots span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-dots span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes blink {
  0%,
  80%,
  100% {
    opacity: 0.3;
  }
  40% {
    opacity: 1;
  }
}
</style>
