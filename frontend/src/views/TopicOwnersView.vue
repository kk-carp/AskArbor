<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { listTopicOwners, upsertTopicOwner } from "@/api/owners";
import OwnerSearchForm, { type OwnerSearchModel } from "@/components/owners/OwnerSearchForm.vue";
import OwnerTable from "@/components/owners/OwnerTable.vue";
import OwnerUpsertDialog from "@/components/owners/OwnerUpsertDialog.vue";
import type { TopicOwnerItem, TopicOwnerUpsertPayload } from "@/types";
import { describeRequestError } from "@/utils/errors";

const allRows = ref<TopicOwnerItem[]>([]);
const loading = ref(false);
const saving = ref(false);
const dialogVisible = ref(false);
const editing = ref<TopicOwnerItem | null>(null);
const page = ref(1);
const pageSize = ref(10);
const query = reactive<OwnerSearchModel>({ keyword: "" });
const applied = reactive<OwnerSearchModel>({ keyword: "" });

const filteredRows = computed(() => {
  const keyword = applied.keyword.trim().toLowerCase();
  if (!keyword) {
    return allRows.value;
  }
  return allRows.value.filter((item) => {
    return (
      item.topic_key.toLowerCase().includes(keyword) ||
      item.topic_name.toLowerCase().includes(keyword) ||
      item.name.toLowerCase().includes(keyword) ||
      item.contact.toLowerCase().includes(keyword)
    );
  });
});

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredRows.value.slice(start, start + pageSize.value);
});

async function loadOwners(): Promise<void> {
  loading.value = true;
  try {
    allRows.value = await listTopicOwners();
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
  page.value = 1;
}

function handleReset(): void {
  query.keyword = "";
  handleSearch();
}

function openCreate(): void {
  editing.value = null;
  dialogVisible.value = true;
}

function openEdit(row: TopicOwnerItem): void {
  editing.value = row;
  dialogVisible.value = true;
}

async function handleSave(payload: TopicOwnerUpsertPayload): Promise<void> {
  saving.value = true;
  try {
    const saved = await upsertTopicOwner(payload);
    ElMessage.success(`已保存：${saved.topic_key}`);
    dialogVisible.value = false;
    await loadOwners();
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
  } finally {
    saving.value = false;
  }
}

onMounted(() => {
  void loadOwners();
});
</script>

<template>
  <div class="page-panel">
    <p class="page-caption">联系方式只来自本表提交值，不调用模型生成。仅教学岗可配置。</p>
    <OwnerSearchForm :model="query" @search="handleSearch" @reset="handleReset" @create="openCreate" />
    <OwnerTable
      :rows="pagedRows"
      :total="filteredRows.length"
      :page="page"
      :page-size="pageSize"
      :loading="loading"
      @update:page="page = $event"
      @update:page-size="pageSize = $event; page = 1"
      @edit="openEdit"
    />
    <OwnerUpsertDialog
      v-model:visible="dialogVisible"
      :submitting="saving"
      :editing="editing"
      @submit="handleSave"
    />
  </div>
</template>
