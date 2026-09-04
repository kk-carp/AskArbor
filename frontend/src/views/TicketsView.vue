<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import { ElMessage } from "element-plus";
import { createTicket, listTickets, replyTicket } from "@/api/tickets";
import CreateTicketDialog from "@/components/tickets/CreateTicketDialog.vue";
import ReplyTicketDialog from "@/components/tickets/ReplyTicketDialog.vue";
import TicketSearchForm, { type TicketSearchModel } from "@/components/tickets/TicketSearchForm.vue";
import TicketTable from "@/components/tickets/TicketTable.vue";
import { useUserStore } from "@/stores/user";
import type { TicketItem } from "@/types";
import { describeRequestError } from "@/utils/errors";

const route = useRoute();
const userStore = useUserStore();
const allRows = ref<TicketItem[]>([]);
const loading = ref(false);
const creating = ref(false);
const replying = ref(false);
const createVisible = ref(false);
const replyVisible = ref(false);
const currentTicket = ref<TicketItem | null>(null);
const page = ref(1);
const pageSize = ref(10);
const highlightId = ref<string | null>(null);

const query = reactive<TicketSearchModel>({ keyword: "", status: "" });
const applied = reactive<TicketSearchModel>({ keyword: "", status: "" });

const canCreate = computed(() => userStore.currentUser?.role === "student");

const filteredRows = computed(() => {
  const keyword = applied.keyword.trim().toLowerCase();
  return allRows.value.filter((item) => {
    const matchKeyword =
      !keyword || item.question.toLowerCase().includes(keyword) || item.id.toLowerCase().includes(keyword);
    const matchStatus = !applied.status || item.status === applied.status;
    return matchKeyword && matchStatus;
  });
});

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredRows.value.slice(start, start + pageSize.value);
});

function canReply(row: TicketItem): boolean {
  const user = userStore.currentUser;
  if (!user || row.status === "replied") {
    return false;
  }
  return user.is_teaching || user.can_manage_documents || row.assignee_id === user.id;
}

async function loadTickets(): Promise<void> {
  loading.value = true;
  try {
    allRows.value = await listTickets();
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
    allRows.value = [];
  } finally {
    loading.value = false;
  }
}

function handleSearch(): void {
  applied.keyword = query.keyword;
  applied.status = query.status;
  page.value = 1;
}

function handleReset(): void {
  query.keyword = "";
  query.status = "";
  handleSearch();
}

async function handleCreate(question: string): Promise<void> {
  creating.value = true;
  try {
    const created = await createTicket(question);
    ElMessage.success(`已建单：${created.id}`);
    createVisible.value = false;
    await loadTickets();
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
  } finally {
    creating.value = false;
  }
}

function openReply(row: TicketItem): void {
  currentTicket.value = row;
  replyVisible.value = true;
}

async function handleReply(reply: string): Promise<void> {
  if (!currentTicket.value) {
    return;
  }
  replying.value = true;
  try {
    await replyTicket(currentTicket.value.id, reply);
    ElMessage.success("已回复");
    replyVisible.value = false;
    await loadTickets();
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
  } finally {
    replying.value = false;
  }
}

watch(
  () => route.query.ticket_id,
  (ticketId) => {
    highlightId.value = typeof ticketId === "string" ? ticketId : null;
    if (highlightId.value) {
      query.keyword = highlightId.value;
      handleSearch();
    }
  },
  { immediate: true },
);

onMounted(() => {
  void loadTickets();
});
</script>

<template>
  <el-card shadow="never">
    <p class="caption">
      仅学员可显式建单；处理人由服务端按班主任计算。列表由接口过滤，回复不会入库。
    </p>
    <el-alert
      v-if="highlightId"
      class="highlight"
      type="info"
      :closable="false"
      :title="`来自问答页的工单：${highlightId}`"
    />
    <TicketSearchForm
      :model="query"
      :can-create="canCreate"
      @search="handleSearch"
      @reset="handleReset"
      @create="createVisible = true"
    />
    <TicketTable
      :rows="pagedRows"
      :total="filteredRows.length"
      :page="page"
      :page-size="pageSize"
      :loading="loading"
      :can-reply="canReply"
      @update:page="page = $event"
      @update:page-size="pageSize = $event; page = 1"
      @reply="openReply"
    />
    <CreateTicketDialog v-model:visible="createVisible" :submitting="creating" @submit="handleCreate" />
    <ReplyTicketDialog
      v-model:visible="replyVisible"
      :submitting="replying"
      :ticket="currentTicket"
      @submit="handleReply"
    />
  </el-card>
</template>

<style scoped>
.caption {
  margin: 0 0 12px;
  color: #909399;
  font-size: 13px;
}

.highlight {
  margin-bottom: 12px;
}
</style>
