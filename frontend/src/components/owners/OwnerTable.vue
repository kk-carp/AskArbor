<script setup lang="ts">
import type { TopicOwnerItem } from "@/types";

defineProps<{
  rows: TopicOwnerItem[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
}>();

const emit = defineEmits<{
  "update:page": [value: number];
  "update:pageSize": [value: number];
  edit: [row: TopicOwnerItem];
}>();
</script>

<template>
  <div>
    <el-table :data="rows" v-loading="loading" stripe empty-text="暂无主题负责人">
      <el-table-column label="主题 key" prop="topic_key" width="140" />
      <el-table-column label="主题名称" prop="topic_name" width="160" />
      <el-table-column label="关键词" prop="keywords" min-width="180" show-overflow-tooltip />
      <el-table-column label="负责人" prop="name" width="140" />
      <el-table-column label="联系方式" prop="contact" min-width="200" show-overflow-tooltip />
      <el-table-column label="操作" width="90" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link @click="emit('edit', row)">编辑</el-button>
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
</style>
