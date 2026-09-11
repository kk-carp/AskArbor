<script setup lang="ts">
import { onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { fetchMetrics } from "@/api/metrics";
import type { MetricsSnapshot } from "@/types";
import { describeRequestError } from "@/utils/errors";

const loading = ref(false);
const metrics = ref<MetricsSnapshot | null>(null);

const cards: { key: keyof MetricsSnapshot; label: string; hint: string }[] = [
  { key: "ask_total", label: "问答次数", hint: "含命中与拒答" },
  { key: "ask_hit", label: "命中", hint: "有依据并作答" },
  { key: "ask_miss", label: "未命中拒答", hint: "知识库没有足够依据" },
  { key: "ask_general_assist", label: "实践参考", hint: "学员概念/实践未命中兜底" },
  { key: "ask_error_502", label: "大模型失败", hint: "502，不是未命中" },
  { key: "ask_error_503", label: "服务未就绪", hint: "503，不是未命中" },
  { key: "ask_429", label: "过于频繁", hint: "被限流挡住" },
  { key: "llm_calls", label: "调用大模型", hint: "拒答不计入，实践参考计入" },
  { key: "prompt_tokens_total", label: "提示 token", hint: "累计" },
  { key: "completion_tokens_total", label: "回复 token", hint: "累计" },
];

async function loadMetrics(): Promise<void> {
  loading.value = true;
  try {
    metrics.value = await fetchMetrics();
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
    metrics.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadMetrics();
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <p class="lead">当前服务进程启动后的累计数字。重启后会从零再计。不是课上评测作业。</p>
      <el-button :loading="loading" @click="loadMetrics">刷新</el-button>
    </div>
    <div v-if="metrics" class="grid">
      <div v-for="card in cards" :key="card.key" class="stat">
        <div class="stat-label">{{ card.label }}</div>
        <div class="stat-value">{{ metrics[card.key] }}</div>
        <div class="stat-hint">{{ card.hint }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page {
  max-width: 960px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

.lead {
  margin: 0;
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.6;
}

.grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 12px;
}

.stat {
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-sm);
  padding: 14px 16px;
}

.stat-label {
  font-size: 13px;
  color: var(--color-muted);
}

.stat-value {
  margin-top: 6px;
  font-size: 24px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  color: var(--color-ink);
}

.stat-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-muted);
}
</style>
