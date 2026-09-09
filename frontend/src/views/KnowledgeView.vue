<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { listDocuments, offlineDocument, uploadCourseZip, uploadDocument } from "@/api/documents";
import CodePackUploadDialog from "@/components/knowledge/CodePackUploadDialog.vue";
import DocumentSearchForm, { type DocumentSearchModel } from "@/components/knowledge/DocumentSearchForm.vue";
import DocumentTable from "@/components/knowledge/DocumentTable.vue";
import DocumentUploadDialog from "@/components/knowledge/DocumentUploadDialog.vue";
import type { DocumentItem, SpaceId } from "@/types";
import { describeRequestError } from "@/utils/errors";

const allRows = ref<DocumentItem[]>([]);
const loading = ref(false);
const uploading = ref(false);
const uploadVisible = ref(false);
const codeUploading = ref(false);
const codeUploadVisible = ref(false);
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

async function handleUpload(payload: { space: SpaceId; files: File[] }): Promise<void> {
  uploading.value = true;
  const succeeded: string[] = [];
  const failed: string[] = [];
  try {
    for (const file of payload.files) {
      try {
        const created = await uploadDocument(payload.space, file);
        succeeded.push(`${created.title}（${created.status}）`);
      } catch (error) {
        const described = describeRequestError(error);
        failed.push(`${file.name}：${described.detail}`);
      }
    }
    if (succeeded.length === 1) {
      ElMessage.success(`上传成功：${succeeded[0]}`);
    } else if (succeeded.length > 1) {
      ElMessage.success(`已上传 ${succeeded.length} 个文档`);
    }
    if (failed.length) {
      ElMessage.error(`上传失败 ${failed.length} 个：${failed.join("；")}`);
    }
    if (succeeded.length) {
      uploadVisible.value = false;
      await loadDocuments();
    }
  } finally {
    uploading.value = false;
  }
}

async function handleCodeUpload(file: File): Promise<void> {
  codeUploading.value = true;
  try {
    const result = await uploadCourseZip(file);
    const readyCount = result.documents.filter((item) => item.status === "ready").length;
    const failedCount = result.documents.filter((item) => item.status === "failed").length;
    const skippedCount = result.skipped.length;
    ElMessage.success(
      `课程代码已写入 student：成功 ${readyCount}，失败 ${failedCount}，跳过 ${skippedCount}`,
    );
    codeUploadVisible.value = false;
    await loadDocuments();
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
  } finally {
    codeUploading.value = false;
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
    <p class="page-caption">仅教学岗可上传与下线。课程代码包固定写入课程空间；失败条目会显示在列表中。</p>
    <DocumentSearchForm
      :model="query"
      @search="handleSearch"
      @reset="handleReset"
      @upload="uploadVisible = true"
      @upload-code="codeUploadVisible = true"
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
    <CodePackUploadDialog
      v-model:visible="codeUploadVisible"
      :submitting="codeUploading"
      @submit="handleCodeUpload"
    />
  </div>
</template>
