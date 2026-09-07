<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { askQuestion, listConversations, listMessages } from "@/api/qa";
import AskComposer from "@/components/qa/AskComposer.vue";
import ConversationList from "@/components/qa/ConversationList.vue";
import MessagePane from "@/components/qa/MessagePane.vue";
import { useAskMetaStore } from "@/stores/askMeta";
import type { ConversationItem, MessageAskMeta, MessageItem } from "@/types";
import { describeRequestError } from "@/utils/errors";

const askMetaStore = useAskMetaStore();
const conversations = ref<ConversationItem[]>([]);
const messages = ref<MessageItem[]>([]);
const currentConversationId = ref<string | null>(null);
const listLoading = ref(false);
const messageLoading = ref(false);
const asking = ref(false);
const pendingQuestion = ref("");
const requestError = ref<{ title: string; detail: string } | null>(null);
const composerRef = ref<{ resetQuestion: () => void } | null>(null);
const messageWrap = ref<HTMLElement | null>(null);

function metaOf(messageId: string): MessageAskMeta | null {
  if (!currentConversationId.value) {
    return null;
  }
  return askMetaStore.getMeta(currentConversationId.value, messageId);
}

async function refreshConversations(): Promise<void> {
  listLoading.value = true;
  try {
    conversations.value = await listConversations();
  } catch (error) {
    requestError.value = describeRequestError(error);
  } finally {
    listLoading.value = false;
  }
}

async function loadMessages(conversationId: string, silent = false): Promise<void> {
  if (!silent) {
    messageLoading.value = true;
  }
  try {
    messages.value = await listMessages(conversationId);
    await scrollToBottom();
  } catch (error) {
    requestError.value = describeRequestError(error);
    messages.value = [];
  } finally {
    messageLoading.value = false;
  }
}

async function selectConversation(id: string | null): Promise<void> {
  currentConversationId.value = id;
  requestError.value = null;
  if (!id) {
    messages.value = [];
    return;
  }
  await loadMessages(id);
}

function startNewConversation(): void {
  currentConversationId.value = null;
  messages.value = [];
  requestError.value = null;
}

async function handleAsk(question: string): Promise<void> {
  asking.value = true;
  requestError.value = null;
  pendingQuestion.value = question;
  await scrollToBottom();
  try {
    const result = await askQuestion(question, currentConversationId.value);
    const conversationId = result.conversation_id;
    if (!conversationId) {
      requestError.value = { title: "问答异常", detail: "响应未返回 conversation_id" };
      return;
    }
    currentConversationId.value = conversationId;
    await refreshConversations();
    await loadMessages(conversationId, true);
    const lastAssistant = [...messages.value].reverse().find((item) => item.role === "assistant");
    if (lastAssistant) {
      askMetaStore.save(conversationId, lastAssistant.id, {
        hit: result.hit,
        ticket_id: result.ticket_id,
        owner: result.owner,
        sources: result.sources,
      });
    }
    composerRef.value?.resetQuestion();
  } catch (error) {
    requestError.value = describeRequestError(error);
  } finally {
    asking.value = false;
    pendingQuestion.value = "";
  }
}

async function scrollToBottom(): Promise<void> {
  await nextTick();
  if (messageWrap.value) {
    messageWrap.value.scrollTop = messageWrap.value.scrollHeight;
  }
}

onMounted(async () => {
  await refreshConversations();
});
</script>

<template>
  <div class="qa-page">
    <aside class="qa-history">
      <ConversationList
        :items="conversations"
        :current-id="currentConversationId"
        :loading="listLoading"
        @select="selectConversation"
        @create="startNewConversation"
      />
    </aside>
    <section class="qa-stage">
      <el-alert
        v-if="requestError"
        :title="requestError.title"
        :description="requestError.detail"
        type="error"
        show-icon
        closable
        class="error-alert"
        @close="requestError = null"
      />
      <div ref="messageWrap" class="messages" v-loading="messageLoading">
        <MessagePane :messages="messages" :meta-of="metaOf" :asking="asking" :pending-question="pendingQuestion" />
      </div>
      <div class="composer-dock">
        <AskComposer ref="composerRef" :loading="asking" @submit="handleAsk" />
      </div>
    </section>
  </div>
</template>

<style scoped>
.qa-page {
  display: grid;
  grid-template-columns: 280px 1fr;
  height: 100%;
  min-height: 0;
  gap: 12px;
  background: var(--color-page);
}

.qa-history {
  min-height: 0;
  height: 100%;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  background: var(--color-card);
  box-shadow: var(--shadow-sm);
}

.qa-stage {
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
}

.error-alert {
  margin: 12px 20px 0;
}

.messages {
  flex: 1;
  overflow: auto;
}

.composer-dock {
  padding: 8px 20px 20px;
  background: var(--color-card);
  border-radius: var(--radius-md);
}

@media (max-width: 960px) {
  .qa-page {
    grid-template-columns: 220px 1fr;
  }
}
</style>
