<script setup lang="ts">
import type { TicketItem } from "@/types";
import { formatDateTime, shortId, ticketStatusLabel } from "@/utils/labels";

defineProps<{
  rows: TicketItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  canReply: (row: TicketItem) => boolean;
}>();

const emit = defineEmits<{
  "update:page": [value: number];
  "update:pageSize": [value: number];
  reply: [row: TicketItem];
}>();
</script>

<template>
  <div>
    <el-table :data="rows" v-loading="loading" stripe empty-text="暂无可见工单">
      <el-table-column label="问题" prop="question" min-width="220" show-overflow-tooltip />
      <el-table-column label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'open' ? 'warning' : 'success'" size="small">
            {{ ticketStatusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="学员" width="180">
        <template #default="{ row }">{{ shortId(row.student_id) }}</template>
      </el-table-column>
      <el-table-column label="处理人" width="180">
        <template #default="{ row }">{{ shortId(row.assignee_id) }}</template>
      </el-table-column>
      <el-table-column label="回复" min-width="180" show-overflow-tooltip>
        <template #default="{ row }">{{ row.reply || "-" }}</template>
      </el-table-column>
      <el-table-column label="更新时间" width="160">
        <template #default="{ row }">{{ formatDateTime(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button v-if="canReply(row)" type="primary" link @click="emit('reply', row)">回复</el-button>
          <span v-else class="muted">{{ row.reply ? "已回复" : "等待回复" }}</span>
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
  color: #909399;
  font-size: 13px;
}
</style>
