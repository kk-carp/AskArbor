<script setup lang="ts">
import type { DocumentItem } from "@/types";
import { documentStatusLabel, shortId, spaceLabel } from "@/utils/labels";

defineProps<{
  rows: DocumentItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
}>();

const emit = defineEmits<{
  "update:page": [value: number];
  "update:pageSize": [value: number];
  offline: [row: DocumentItem];
}>();

function statusType(status: DocumentItem["status"]): "success" | "info" | "warning" | "danger" {
  if (status === "ready") {
    return "success";
  }
  if (status === "failed") {
    return "danger";
  }
  if (status === "offline") {
    return "info";
  }
  return "warning";
}
</script>

<template>
  <div>
    <el-table :data="rows" v-loading="loading" empty-text="暂无文档">
      <el-table-column label="标题" prop="title" min-width="180" />
      <el-table-column label="空间" width="120">
        <template #default="{ row }">{{ spaceLabel(row.space_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ documentStatusLabel(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="切片数" prop="chunk_count" width="90" />
      <el-table-column label="失败原因" min-width="180">
        <template #default="{ row }">{{ row.error || "-" }}</template>
      </el-table-column>
      <el-table-column label="文档 ID" width="120">
        <template #default="{ row }">{{ shortId(row.id) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button
            v-if="row.status !== 'offline'"
            type="danger"
            link
            @click="emit('offline', row)"
          >
            下线
          </el-button>
          <span v-else class="muted">已下线</span>
        </template>
      </el-table-column>
    </el-table>
    <div class="pager">
      <el-pagination
        background
        layout="total, sizes, prev, pager, next"
        :total="total"
        :current-page="page"
        :page-size="pageSize"
        :page-sizes="[10, 20, 50]"
        @current-change="emit('update:page', $event)"
        @size-change="emit('update:pageSize', $event)"
      />
    </div>
  </div>
</template>

<style scoped>
.pager {
  display: flex;
  justify-content: flex-end;
  margin-top: 12px;
}

.muted {
  color: var(--color-muted);
  font-size: 13px;
}
</style>
