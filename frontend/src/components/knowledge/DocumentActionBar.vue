<script setup lang="ts">
defineProps<{
  selectedCount: number;
  batching: boolean;
}>();

const emit = defineEmits<{
  upload: [];
  uploadCode: [];
  batchOffline: [];
  batchDelete: [];
}>();
</script>

<template>
  <div class="action-rail">
    <div class="cluster">
      <el-button type="primary" @click="emit('upload')">上传文档</el-button>
      <el-button @click="emit('uploadCode')">上传课程代码包</el-button>
    </div>
    <div class="cluster">
      <span class="count" aria-live="polite">
        {{ selectedCount ? `已选 ${selectedCount} 份` : "未勾选" }}
      </span>
      <el-button :disabled="batching || !selectedCount" :loading="batching" @click="emit('batchOffline')">
        批量下线
      </el-button>
      <el-button type="danger" :disabled="batching || !selectedCount" :loading="batching" @click="emit('batchDelete')">
        批量删除
      </el-button>
    </div>
  </div>
</template>

<style scoped>
.action-rail {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px 16px;
  flex-wrap: nowrap;
  padding: 4px 0 14px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--color-line);
}

.cluster {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 8px;
}

.count {
  min-width: 6.5em;
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.4;
  font-variant-numeric: tabular-nums;
}

@media (max-width: 720px) {
  .action-rail {
    align-items: stretch;
    flex-wrap: wrap;
  }

  .cluster {
    width: 100%;
    flex-wrap: wrap;
  }

  .count {
    min-width: 0;
    flex: 1;
  }
}
</style>
