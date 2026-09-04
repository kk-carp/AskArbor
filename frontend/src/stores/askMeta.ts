import { defineStore } from "pinia";
import { ref } from "vue";
import type { MessageAskMeta } from "@/types";

const STORAGE_KEY = "fde_ask_meta_v1";

type MetaMap = Record<string, Record<string, MessageAskMeta>>;

function readStorage(): MetaMap {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as MetaMap;
    return parsed && typeof parsed === "object" ? parsed : {};
  } catch {
    return {};
  }
}

function writeStorage(value: MetaMap): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
}

/** 按会话 + 助手消息 id 缓存 /ask 的 hit、来源、工单与负责人 */
export const useAskMetaStore = defineStore("askMeta", () => {
  const cache = ref<MetaMap>(readStorage());

  function save(conversationId: string, messageId: string, meta: MessageAskMeta): void {
    const next = { ...cache.value };
    next[conversationId] = { ...(next[conversationId] || {}), [messageId]: meta };
    cache.value = next;
    writeStorage(next);
  }

  function getMeta(conversationId: string, messageId: string): MessageAskMeta | null {
    return cache.value[conversationId]?.[messageId] ?? null;
  }

  return { cache, save, getMeta };
});
