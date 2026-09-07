<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import { fetchLearningPath } from "@/api/learningPath";
import type { ExternalKind, LearningPathResponse } from "@/types";
import { describeRequestError } from "@/utils/errors";

const loading = ref(false);
const data = ref<LearningPathResponse | null>(null);

const searchAlert = computed(() => {
  const errorType = data.value?.error_type;
  if (errorType === "search_timeout") {
    return "课外搜索超时。下面课内资料仍可用，这不是知识库未命中。";
  }
  if (errorType === "search_unavailable") {
    return "课外搜索暂不可用。下面课内资料仍可用，这不是知识库未命中。";
  }
  return "";
});

function kindLabel(kind: ExternalKind): string {
  if (kind === "paper") {
    return "论文";
  }
  if (kind === "oss") {
    return "开源";
  }
  return "文档";
}

async function loadPath(refresh = false): Promise<void> {
  loading.value = true;
  try {
    data.value = await fetchLearningPath(refresh);
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
    data.value = null;
  } finally {
    loading.value = false;
  }
}

onMounted(() => {
  void loadPath(false);
});
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h1>学习路径</h1>
        <p class="hint">根据近期提问推荐课程资料，并补充开源、免费的课外阅读与论文。</p>
        <p v-if="data?.from_cache" class="cache-hint">当前为缓存结果；点击「重新搜索」可按最新提问更新。</p>
      </div>
      <el-button type="primary" :loading="loading" @click="loadPath(true)">重新搜索</el-button>
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

    <el-row :gutter="16">
      <el-col :xs="24" :md="12">
        <el-card shadow="never" class="panel">
          <template #header>课内资料</template>
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
          <template #header>课外阅读（开源 / 免费）</template>
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

.cache-hint {
  margin: 4px 0 0;
  color: var(--color-muted);
  font-size: 12px;
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
