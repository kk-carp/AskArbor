<script setup lang="ts">
export interface OwnerSearchModel {
  keyword: string;
}

defineProps<{
  model: OwnerSearchModel;
}>();

const emit = defineEmits<{
  search: [];
  reset: [];
  create: [];
}>();
</script>

<template>
  <el-form :inline="true" :model="model">
    <el-form-item label="关键词">
      <el-input v-model="model.keyword" placeholder="主题 / 负责人" clearable />
    </el-form-item>
    <el-form-item>
      <el-button type="primary" @click="emit('search')">搜索</el-button>
      <el-button @click="emit('reset')">重置</el-button>
      <el-button type="success" @click="emit('create')">新增 / 更新</el-button>
    </el-form-item>
  </el-form>
</template>
