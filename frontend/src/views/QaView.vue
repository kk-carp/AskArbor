<script setup lang="ts">
import { nextTick, onMounted, ref } from "vue";
import { askQuestionStream, askWithImage, listConversations, listMessages } from "@/api/qa";
import AskComposer from "@/components/qa/AskComposer.vue";
import ConversationList from "@/components/qa/ConversationList.vue";
import DisclaimerNote from "@/components/DisclaimerNote.vue";
import MessagePane from "@/components/qa/MessagePane.vue";
import { useAskMetaStore } from "@/stores/askMeta";
import { useMessageImageStore } from "@/stores/messageImages";
import type { AskResponse, ConversationItem, MessageAskMeta, MessageItem, SourceItem } from "@/types";
import { describeRequestError } from "@/utils/errors";

const askMetaStore = useAskMetaStore();
const messageImageStore = useMessageImageStore();
const conversations = ref<ConversationItem[]>([]);
const messages = ref<MessageItem[]>([]);
const currentConversationId = ref<string | null>(null);
const listLoading = ref(false);
const messageLoading = ref(false);
const asking = ref(false);
const pendingQuestion = ref("");
const pendingImageUrl = ref<string | null>(null);
const pendingAnswer = ref("");
const pendingSources = ref<SourceItem[]>([]);
const requestError = ref<{ title: string; detail: string } | null>(null);
const messageWrap = ref<HTMLElement | null>(null);

function metaOf(messageId: string): MessageAskMeta | null {
  if (!currentConversationId.value) {
    return null;
  }
  return askMetaStore.getMeta(currentConversationId.value, messageId);
}

function imageOf(messageId: string): string | null {
  if (!currentConversationId.value) {
    return null;
  }
  return messageImageStore.getUrl(currentConversationId.value, messageId);
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

async function applyAskResult(result: AskResponse, localImageUrl: string | null): Promise<void> {
  if (result.error_type === "ocr_failed") {
    requestError.value = {
      title: "图片识别失败",
      detail: result.answer || "请换更清晰的截图或改用文字提问。这不是知识库未命中。",
    };
    return;
  }

  const conversationId = result.conversation_id;
  if (!conversationId) {
    requestError.value = { title: "问答异常", detail: "响应未返回 conversation_id" };
    return;
  }
  currentConversationId.value = conversationId;
  await refreshConversations();
  await loadMessages(conversationId, true);
  const lastAssistant = [...messages.value].reverse().find((item) => item.role === "assistant");
  const lastUser = [...messages.value].reverse().find((item) => item.role === "user");
  if (lastAssistant) {
    askMetaStore.save(conversationId, lastAssistant.id, {
      hit: result.hit,
      ticket_id: result.ticket_id,
      owner: result.owner,
      sources: result.sources,
      error_type: result.error_type ?? null,
    });
  }
  if (lastUser && localImageUrl) {
    messageImageStore.save(conversationId, lastUser.id, localImageUrl);
    pendingImageUrl.value = null;
  }
}

async function handleAsk(payload: string | { question: string; image: File | null }): Promise<void> {
  const data =
    typeof payload === "string" ? { question: payload, image: null as File | null } : payload;
  const question = (data.question ?? "").trim();
  const image = data.image ?? null;
  if (!question && !image) {
    requestError.value = { title: "请求无效", detail: "请输入问题或上传截图" };
    return;
  }

  asking.value = true;
  requestError.value = null;
  pendingQuestion.value = image ? question || "截图提问" : question;
  pendingAnswer.value = "";
  pendingSources.value = [];
  if (pendingImageUrl.value) {
    URL.revokeObjectURL(pendingImageUrl.value);
    pendingImageUrl.value = null;
  }
  const localImageUrl = image ? URL.createObjectURL(image) : null;
  pendingImageUrl.value = localImageUrl;
  await scrollToBottom();
  try {
    if (image) {
      const result = await askWithImage(image, question || null, currentConversationId.value);
      await applyAskResult(result, localImageUrl);
      return;
    }

    let finalResult: AskResponse | null = null;
    await askQuestionStream(question, currentConversationId.value, {
      onMeta: (meta) => {
        pendingSources.value = meta.sources || [];
        if (meta.conversation_id) {
          currentConversationId.value = meta.conversation_id;
        }
      },
      onDelta: (chunk) => {
        pendingAnswer.value += chunk;
        void scrollToBottom();
      },
      onFinal: (result) => {
        finalResult = result;
        pendingAnswer.value = result.answer || pendingAnswer.value;
        if (result.sources?.length) {
          pendingSources.value = result.sources;
        }
      },
    });
    const completed = finalResult;
    if (!completed) {
      requestError.value = { title: "问答异常", detail: "流式响应未返回结果" };
      return;
    }
    await applyAskResult(completed, null);
  } catch (error) {
    requestError.value = describeRequestError(error);
  } finally {
    asking.value = false;
    pendingQuestion.value = "";
    pendingAnswer.value = "";
    pendingSources.value = [];
    if (pendingImageUrl.value) {
      URL.revokeObjectURL(pendingImageUrl.value);
      pendingImageUrl.value = null;
    }
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
        <MessagePane
          :messages="messages"
          :meta-of="metaOf"
          :image-of="imageOf"
          :asking="asking"
          :pending-question="pendingQuestion"
          :pending-image-url="pendingImageUrl"
          :pending-answer="pendingAnswer"
          :pending-sources="pendingSources"
        />
      </div>
      <div class="composer-dock">
        <AskComposer :loading="asking" @submit="handleAsk" />
        <DisclaimerNote class="qa-disclaimer" />
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

.qa-disclaimer {
  margin-top: 8px;
  text-align: center;
}

@media (max-width: 960px) {
  .qa-page {
    grid-template-columns: 220px 1fr;
  }
}
</style>
