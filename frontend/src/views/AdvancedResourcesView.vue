<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { planAdvancedResourcesStream } from "@/api/advancedResources";
import type {
  AdvancedResourcesPlanResponse,
  AdvancedResourcesReport,
  AdvancedResourceStep,
} from "@/types";
import { ApiError } from "@/types";
import { describeRequestError } from "@/utils/errors";

const loading = ref(false);
const steps = ref<AdvancedResourceStep[]>([]);
const report = ref<AdvancedResourcesReport | null>(null);
const meta = ref<Pick<
  AdvancedResourcesPlanResponse,
  "weak_points" | "course" | "external" | "error_type" | "message" | "from_cache"
> | null>(null);
const trajectoryOpen = ref(true);
let abort: AbortController | null = null;

const searchAlert = computed(() => {
  const errorType = meta.value?.error_type;
  if (errorType === "search_timeout") {
    return "课外搜索超时。课内推荐仍可用；这不是知识库未命中。";
  }
  if (errorType === "search_unavailable") {
    return "课外搜索暂不可用。课内推荐仍可用；这不是知识库未命中。";
  }
  return "";
});

function stepTitle(step: AdvancedResourceStep): string {
  const map: Record<string, string> = {
    summarize_weak_points: "归纳薄弱点",
    search_course: "课内检索",
    search_external: "课外搜索",
    judge_relevance: "相关性判定",
    analyze_capability: "能力分析",
    compose_report: "撰写推荐文章",
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
  if (step.tool === "compose_report") {
    return d.has_report ? `成文 · ${String(d.material_count ?? 0)} 条资料` : "成文降级";
  }
  if (step.tool === "analyze_capability") {
    return "已生成能力画像";
  }
  return step.message || "";
}

async function runPlan(refresh = false): Promise<void> {
  abort?.abort();
  abort = new AbortController();
  loading.value = true;
  if (refresh) {
    steps.value = [];
    report.value = null;
    meta.value = null;
  }
  trajectoryOpen.value = true;

  try {
    await planAdvancedResourcesStream(
      {
        signal: abort.signal,
        onStep: (step) => {
          steps.value = [...steps.value, step];
        },
        onFinal: (payload) => {
          report.value = payload.report;
          meta.value = {
            weak_points: payload.weak_points,
            course: payload.course,
            external: payload.external,
            error_type: payload.error_type,
            message: payload.message,
            from_cache: payload.from_cache,
          };
          if (payload.steps?.length) {
            steps.value = payload.steps;
          }
          if (payload.from_cache) {
            trajectoryOpen.value = false;
          }
        },
        onError: (payload) => {
          const status = payload.status || 500;
          const detail = payload.detail || "进阶资料推荐失败";
          const described = describeRequestError(new ApiError(status, detail));
          ElMessage.error(`${described.title}：${described.detail}`);
        },
      },
      { refresh },
    );
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return;
    }
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void runPlan(false);
});

onUnmounted(() => {
  abort?.abort();
});
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <h1>进阶资料推荐</h1>
        <p class="hint">根据近期提问生成学习诊断与进阶建议；资料均来自课程库与白名单课外检索。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="runPlan(true)">重新生成</el-button>
    </header>

    <p v-if="meta?.from_cache" class="cache-hint">当前为缓存结果；点击「重新生成」可按最新提问更新。</p>

    <el-alert
      v-if="searchAlert"
      class="alert"
      type="warning"
      :closable="false"
      :title="searchAlert"
    />
    <el-alert
      v-else-if="meta?.message && !report"
      class="alert"
      type="info"
      :closable="false"
      :title="meta.message"
    />

    <section class="trajectory" :class="{ busy: loading }">
      <button type="button" class="traj-toggle" @click="trajectoryOpen = !trajectoryOpen">
        <span>调用轨迹{{ loading ? "（生成中…）" : "" }}</span>
        <span class="traj-count">{{ steps.length }} 步</span>
      </button>
      <ol v-show="trajectoryOpen" class="steps">
        <li v-for="(step, index) in steps" :key="`${step.tool}-${index}`">
          <div class="step-title">
            <span>{{ index + 1 }}. {{ stepTitle(step) }}</span>
            <el-tag size="small" :type="step.ok ? 'success' : 'danger'" effect="plain">
              {{ step.ok ? "ok" : "fail" }}
            </el-tag>
          </div>
          <div v-if="stepDetail(step)" class="step-detail">{{ stepDetail(step) }}</div>
        </li>
        <li v-if="loading" class="step-pending">正在执行下一步…</li>
      </ol>
    </section>

    <article v-if="report" class="article">
      <h2 class="article-title">{{ report.title }}</h2>

      <section class="block">
        <h3>目前能力分析</h3>
        <p class="prose">{{ report.capability_analysis || "暂无足够提问记录生成画像。" }}</p>
      </section>

      <section v-if="report.weak_points_detail.length" class="block">
        <h3>可能的薄弱点</h3>
        <ul class="weak-list">
          <li v-for="item in report.weak_points_detail" :key="item.topic">
            <div class="weak-topic">{{ item.topic }}</div>
            <p v-if="item.why" class="prose muted">{{ item.why }}</p>
          </li>
        </ul>
      </section>

      <section class="block">
        <h3>推荐资料与理由</h3>
        <el-empty
          v-if="!report.materials.length"
          description="暂无通过筛选的资料"
          :image-size="56"
        />
        <ul v-else class="material-list">
          <li v-for="item in report.materials" :key="item.ref_id">
            <div class="material-head">
              <a
                v-if="item.url"
                class="material-title link"
                :href="item.url"
                target="_blank"
                rel="noopener noreferrer"
              >
                {{ item.title || item.url }}
              </a>
              <div v-else class="material-title">{{ item.title || "课内资料" }}</div>
              <el-tag size="small" effect="plain">
                {{ item.channel === "external" ? "课外" : "课内" }}
              </el-tag>
            </div>
            <div v-if="item.path || item.host" class="meta">
              {{ item.path || item.host }}
            </div>
            <p class="prose"><strong>为什么推荐：</strong>{{ item.reason }}</p>
            <p class="prose muted"><strong>怎么用：</strong>{{ item.how_to_use }}</p>
          </li>
        </ul>
      </section>

      <section v-if="report.next_steps.length" class="block">
        <h3>下一步做什么</h3>
        <ol class="next-list">
          <li v-for="(item, index) in report.next_steps" :key="index">{{ item }}</li>
        </ol>
      </section>
    </article>

    <section
      v-else-if="!loading && meta && (meta.course.length || meta.external.length)"
      class="fallback"
    >
      <el-alert
        type="info"
        :closable="false"
        title="成文未完成，仍展示已筛选的资料列表。"
        class="alert"
      />
      <ul class="material-list">
        <li v-for="item in meta.course" :key="item.document_id">
          <div class="material-title">{{ item.title }}</div>
          <div class="meta">{{ item.path || "课程空间" }}</div>
        </li>
        <li v-for="item in meta.external" :key="item.url">
          <a class="material-title link" :href="item.url" target="_blank" rel="noopener noreferrer">
            {{ item.title }}
          </a>
          <div class="meta">{{ item.host }}</div>
        </li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.page {
  max-width: 760px;
}

.page-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 20px;
}

h1 {
  margin: 0;
  font-size: 22px;
  font-weight: 700;
}

.hint {
  margin: 8px 0 0;
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.5;
}

.cache-hint {
  margin: -8px 0 16px;
  color: var(--color-muted);
  font-size: 12px;
}

.alert {
  margin-bottom: 16px;
}

.trajectory {
  margin-bottom: 24px;
  border-top: 1px solid var(--color-line);
  border-bottom: 1px solid var(--color-line);
  padding: 8px 0;
}

.trajectory.busy {
  border-color: color-mix(in srgb, var(--color-primary) 35%, var(--color-line));
}

.traj-toggle {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  border: 0;
  background: transparent;
  padding: 8px 0;
  cursor: pointer;
  font: inherit;
  font-weight: 600;
  color: var(--color-ink);
}

.traj-count {
  font-weight: 500;
  font-size: 12px;
  color: var(--color-muted);
}

.steps {
  margin: 0;
  padding: 0 0 8px 18px;
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

.step-detail,
.step-pending {
  margin-top: 4px;
  color: var(--color-muted);
  font-size: 12px;
  line-height: 1.5;
}

.article-title {
  margin: 0 0 20px;
  font-size: 26px;
  font-weight: 700;
  line-height: 1.3;
}

.block {
  margin-bottom: 28px;
}

.block h3 {
  margin: 0 0 10px;
  font-size: 16px;
  font-weight: 650;
}

.prose {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-ink);
}

.prose + .prose {
  margin-top: 8px;
}

.muted {
  color: var(--color-muted);
}

.weak-list,
.material-list,
.next-list {
  margin: 0;
  padding: 0;
  list-style: none;
}

.next-list {
  padding-left: 18px;
  list-style: decimal;
}

.next-list li {
  margin-top: 8px;
  line-height: 1.6;
  font-size: 14px;
}

.weak-list li + li,
.material-list li + li {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--color-line);
}

.weak-topic,
.material-title {
  font-weight: 650;
  color: var(--color-ink);
}

.material-head {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.link:hover {
  color: var(--color-primary);
}

.meta {
  margin-top: 4px;
  margin-bottom: 8px;
  font-size: 12px;
  color: var(--color-muted);
}

.fallback {
  margin-top: 8px;
}
</style>
