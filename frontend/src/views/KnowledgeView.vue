<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listDocuments, offlineDocument, uploadDocument } from "@/api/documents";
import DocumentSearchForm, { type DocumentSearchModel } from "@/components/knowledge/DocumentSearchForm.vue";
import DocumentTable from "@/components/knowledge/DocumentTable.vue";
import DocumentUploadDialog from "@/components/knowledge/DocumentUploadDialog.vue";
import type { DocumentItem, SpaceId } from "@/types";
import { describeRequestError } from "@/utils/errors";

const allRows = ref<DocumentItem[]>([]);
const loading = ref(false);
const uploading = ref(false);
const uploadVisible = ref(false);
const page = ref(1);
const pageSize = ref(10);

const query = reactive<DocumentSearchModel>({
  keyword: "",
  space_id: "",
  status: "",
});

const applied = reactive<DocumentSearchModel>({
  keyword: "",
  space_id: "",
  status: "",
});

const filteredRows = computed(() => {
  const keyword = applied.keyword.trim().toLowerCase();
  return allRows.value.filter((item) => {
    const matchKeyword = !keyword || item.title.toLowerCase().includes(keyword);
    const matchSpace = !applied.space_id || item.space_id === applied.space_id;
    const matchStatus = !applied.status || item.status === applied.status;
    return matchKeyword && matchSpace && matchStatus;
  });
});

const pagedRows = computed(() => {
  const start = (page.value - 1) * pageSize.value;
  return filteredRows.value.slice(start, start + pageSize.value);
});

async function loadDocuments(): Promise<void> {
  loading.value = true;
  try {
    allRows.value = await listDocuments();
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
  applied.space_id = query.space_id;
  applied.status = query.status;
  page.value = 1;
}

function handleReset(): void {
  query.keyword = "";
  query.space_id = "";
  query.status = "";
  handleSearch();
}

async function handleUpload(payload: { space: SpaceId; file: File }): Promise<void> {
  uploading.value = true;
  try {
    const created = await uploadDocument(payload.space, payload.file);
    ElMessage.success(`上传成功：${created.title}，状态 ${created.status}`);
    uploadVisible.value = false;
    await loadDocuments();
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
  } finally {
    uploading.value = false;
  }
}

async function handleOffline(row: DocumentItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认下线「${row.title}」？下线后不可检索。`, "下线确认", {
      type: "warning",
      confirmButtonText: "下线",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await offlineDocument(row.id);
    ElMessage.success("已下线");
    await loadDocuments();
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
  }
}

onMounted(() => {
  void loadDocuments();
});
</script>

<template>
  <div class="page-panel">
    <p class="page-caption">仅教学岗可上传与下线。列表状态来自服务端，失败原因原样展示。</p>
    <DocumentSearchForm
      :model="query"
      @search="handleSearch"
      @reset="handleReset"
      @upload="uploadVisible = true"
    />
    <DocumentTable
      :rows="pagedRows"
      :total="filteredRows.length"
      :page="page"
      :page-size="pageSize"
      :loading="loading"
      @update:page="page = $event"
      @update:page-size="pageSize = $event; page = 1"
      @offline="handleOffline"
    />
    <DocumentUploadDialog
      v-model:visible="uploadVisible"
      :submitting="uploading"
      @submit="handleUpload"
    />
  </div>
</template>
