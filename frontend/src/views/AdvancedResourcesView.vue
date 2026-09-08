<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { planAdvancedResources } from "@/api/advancedResources";
import type { AdvancedResourcesPlanResponse, AdvancedResourceStep, ExternalKind } from "@/types";
import { describeRequestError } from "@/utils/errors";

const loading = ref(false);
const data = ref<AdvancedResourcesPlanResponse | null>(null);

const searchAlert = computed(() => {
  const errorType = data.value?.error_type;
  if (errorType === "search_timeout") {
    return "课外搜索超时。课内推荐仍可用；这不是知识库未命中。";
  }
  if (errorType === "search_unavailable") {
    return "课外搜索暂不可用。课内推荐仍可用；这不是知识库未命中。";
  }
  return "";
});

function kindLabel(kind: ExternalKind): string {
  if (kind === "paper") return "论文";
  if (kind === "oss") return "开源";
  return "文档";
}

function stepTitle(step: AdvancedResourceStep): string {
  const map: Record<string, string> = {
    summarize_weak_points: "归纳薄弱点",
    search_course: "课内检索",
    search_external: "课外搜索",
    judge_relevance: "相关性判定",
  };
  return map[step.tool] || step.tool;
}

function stepDetail(step: AdvancedResourceStep): string {
  const d = step.data || {};
  if (step.tool === "search_course") {
    return `搜索词：${String(d.query ?? "")} · 候选 ${String(d.candidate_count ?? 0)}`;
  }
  if (step.tool === "search_external") {
    return `候选 ${String(d.candidate_count ?? 0)}`;
  }
  if (step.tool === "judge_relevance") {
    const refine = d.need_refine ? ` · 建议改写：${String(d.refined_query ?? "")}` : "";
    const reason = d.reason ? ` · ${String(d.reason)}` : "";
    return `保留 ${String(d.keep ?? 0)}${refine}${reason}`;
  }
  if (step.tool === "summarize_weak_points") {
    const points = d.weak_points;
    return Array.isArray(points) ? `识别 ${points.length} 个` : "";
  }
  return step.message || "";
}

async function runPlan(): Promise<void> {
  loading.value = true;
  try {
    data.value = await planAdvancedResources();
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
    data.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void runPlan();
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>进阶资料推荐</h1>
        <p class="hint">
          按薄弱点分步检索，并由模型过滤无关结果；必要时改写搜索词再搜。推荐列表已去掉明显跑题条目。
        </p>
      </div>
      <el-button type="primary" :loading="loading" @click="runPlan">重新推荐</el-button>
    </div>

    <el-alert
      v-if="searchAlert"
      class="alert"
      type="warning"
      :closable="false"
      :title="searchAlert"
    />
    <el-alert
      v-else-if="data?.message"
      class="alert"
      type="info"
      :closable="false"
      :title="data.message"
    />

    <section v-if="data?.weak_points.length" class="block">
      <h2>识别到的薄弱点</h2>
      <div class="tags">
        <el-tag v-for="item in data.weak_points" :key="item" effect="plain">{{ item }}</el-tag>
      </div>
    </section>

    <section v-if="data?.steps.length" class="block">
      <h2>调用轨迹</h2>
      <ol class="steps">
        <li v-for="(step, index) in data.steps" :key="`${step.tool}-${index}`">
          <div class="step-title">
            <span>{{ index + 1 }}. {{ stepTitle(step) }}</span>
            <el-tag size="small" :type="step.ok ? 'success' : 'danger'" effect="plain">
              {{ step.ok ? "ok" : "fail" }}
            </el-tag>
          </div>
          <div v-if="stepDetail(step)" class="step-detail">{{ stepDetail(step) }}</div>
        </li>
      </ol>
    </section>

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="panel">
          <template #header>课内资料（已过滤）</template>
          <el-empty v-if="!data?.course.length" description="暂无课内推荐" :image-size="64" />
          <ul v-else class="list">
            <li v-for="item in data.course" :key="item.document_id">
              <div class="title">{{ item.title }}</div>
              <div class="meta">{{ item.path || "课程空间" }}</div>
            </li>
          </ul>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="panel">
          <template #header>课外阅读（已过滤）</template>
          <el-empty v-if="!data?.external.length" description="暂无课外推荐" :image-size="64" />
          <ul v-else class="list">
            <li v-for="item in data.external" :key="item.url">
              <a class="title link" :href="item.url" target="_blank" rel="noopener noreferrer">
                {{ item.title }}
              </a>
              <div class="meta">
                <el-tag size="small" effect="plain">{{ kindLabel(item.kind) }}</el-tag>
                <span>{{ item.host }}</span>
              </div>
              <p v-if="item.snippet" class="snippet">{{ item.snippet }}</p>
            </li>
          </ul>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.page {
  max-width: 1080px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}

h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 700;
}

h2 {
  margin: 0 0 8px;
  font-size: 14px;
  font-weight: 600;
}

.hint {
  margin: 6px 0 0;
  color: var(--color-muted);
  font-size: 13px;
}

.alert {
  margin-bottom: 16px;
}

.block {
  margin-bottom: 16px;
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.steps {
  margin: 0;
  padding-left: 18px;
  color: var(--color-ink);
  font-size: 13px;
}

.steps li + li {
  margin-top: 10px;
}

.step-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}

.step-detail {
  margin-top: 4px;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.5;
}

.panel {
  margin-bottom: 16px;
}

.list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.list li + li {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--color-line);
}

.title {
  font-weight: 600;
  color: var(--color-ink);
}

.link:hover {
  color: var(--color-primary);
}

.meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 12px;
  color: var(--color-muted);
}

.snippet {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--color-muted);
  line-height: 1.5;
}
</style>
