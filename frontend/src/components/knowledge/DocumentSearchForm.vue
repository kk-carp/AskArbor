<script setup lang="ts">
import { reactive } from "vue";
import type { DocumentStatus, SpaceId } from "@/types";

export interface DocumentSearchModel {
  keyword: string;
  space_id: SpaceId | "";
  status: DocumentStatus | "";
}

const props = defineProps<{
  model: DocumentSearchModel;
}>();

const emit = defineEmits<{
  search: [];
  reset: [];
}>();

const inner = reactive(props.model);
</script>

<template>
  <el-form :inline="true" :model="inner" class="toolbar" @submit.prevent="emit('search')">
    <el-form-item label="标题">
      <el-input v-model="inner.keyword" placeholder="按标题查找" clearable @keyup.enter="emit('search')" />
    </el-form-item>
    <el-form-item label="空间">
      <el-select v-model="inner.space_id" placeholder="全部" clearable style="width: 140px">
        <el-option label="课程空间" value="student" />
        <el-option label="内部空间" value="company" />
      </el-select>
    </el-form-item>
    <el-form-item label="状态">
      <el-select v-model="inner.status" placeholder="全部" clearable style="width: 140px">
        <el-option label="处理中" value="processing" />
        <el-option label="可检索" value="ready" />
        <el-option label="失败" value="failed" />
        <el-option label="已下线" value="offline" />
      </el-select>
    </el-form-item>
    <el-form-item>
      <el-button type="primary" native-type="submit">查找</el-button>
      <el-button @click="emit('reset')">清空条件</el-button>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.toolbar {
  margin-bottom: 4px;
}

.toolbar :deep(.el-form-item) {
  margin-bottom: 10px;
}
</style>
