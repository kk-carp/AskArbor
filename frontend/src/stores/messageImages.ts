import { defineStore } from "pinia";
import { ref } from "vue";

type ImageMap = Record<string, Record<string, string>>;

/** 会话内用户消息的截图预览（仅本页内存，刷新后不保留） */
export const useMessageImageStore = defineStore("messageImages", () => {
  const cache = ref<ImageMap>({});

  function save(conversationId: string, messageId: string, objectUrl: string): void {
    const next = { ...cache.value };
    const bucket = { ...(next[conversationId] || {}) };
    const prev = bucket[messageId];
    if (prev && prev !== objectUrl) {
      URL.revokeObjectURL(prev);
    }
    bucket[messageId] = objectUrl;
    next[conversationId] = bucket;
    cache.value = next;
  }

  function getUrl(conversationId: string, messageId: string): string | null {
    return cache.value[conversationId]?.[messageId] ?? null;
  }

  function clearConversation(conversationId: string): void {
    const bucket = cache.value[conversationId];
    if (!bucket) {
      return;
    }
    for (const url of Object.values(bucket)) {
      URL.revokeObjectURL(url);
    }
    const next = { ...cache.value };
    delete next[conversationId];
    cache.value = next;
  }

  return { cache, save, getUrl, clearConversation };
});
