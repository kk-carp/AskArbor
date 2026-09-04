<script setup lang="ts">
import type { TicketStatus } from "@/types";

export interface TicketSearchModel {
  keyword: string;
  status: TicketStatus | "";
}

defineProps<{
  model: TicketSearchModel;
  canCreate: boolean;
}>();

const emit = defineEmits<{
  search: [];
  reset: [];
  create: [];
}>();
</script>

<template>
  <el-form :inline="true" :model="model" class="toolbar">
    <el-form-item label="关键词">
      <el-input v-model="model.keyword" placeholder="问题或工单号" clearable />
    </el-form-item>
    <el-form-item label="状态">
      <el-select v-model="model.status" placeholder="全部" clearable style="width: 140px">
        <el-option label="待回复" value="open" />
        <el-option label="已回复" value="replied" />
      </el-select>
    </el-form-item>
    <el-form-item>
      <el-button type="primary" @click="emit('search')">搜索</el-button>
      <el-button @click="emit('reset')">重置</el-button>
      <el-button v-if="canCreate" type="success" @click="emit('create')">创建工单</el-button>
    </el-form-item>
  </el-form>
</template>
