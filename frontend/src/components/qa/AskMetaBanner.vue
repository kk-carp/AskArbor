<script setup lang="ts">
import { computed } from "vue";
import { useRouter } from "vue-router";
import type { MessageAskMeta } from "@/types";

const props = defineProps<{
  meta: MessageAskMeta | null;
}>();

const router = useRouter();

const showOwner = computed(() => props.meta !== null && props.meta.owner !== null);
const showTicket = computed(() => Boolean(props.meta?.ticket_id));
const isOcrFailed = computed(() => props.meta?.error_type === "ocr_failed");
const isScreenshotOnly = computed(() => props.meta?.error_type === "screenshot_only");
const hitLabel = computed(() => {
  if (isOcrFailed.value) {
    return "图片识别失败";
  }
  if (isScreenshotOnly.value) {
    return "已依据截图文字";
  }
  if (props.meta?.hit === true) {
    return "已命中知识库";
  }
  if (props.meta?.hit === false) {
    return "未命中知识库";
  }
  return "";
});
const pillClass = computed(() => {
  if (isOcrFailed.value) {
    return "tool";
  }
  if (isScreenshotOnly.value) {
    return "shot";
  }
  return props.meta?.hit ? "hit" : "miss";
});

function goTicket(): void {
  if (!props.meta?.ticket_id) {
    return;
  }
  void router.push({ name: "work-orders", query: { ticket_id: props.meta.ticket_id } });
}
</script>

<template>
  <div v-if="meta && hitLabel" class="meta-banner">
    <span class="hit-pill" :class="pillClass">
      {{ hitLabel }}
    </span>
    <div v-if="isOcrFailed" class="note">这不是知识库未命中，不会自动创建学员工单。</div>
    <div v-if="isScreenshotOnly" class="note">
      知识库未命中；已根据截图文字解释操作/报错。课表、成绩、制度仍只信知识库。
    </div>
    <div v-if="showTicket" class="note">
      <span>已自动创建学员工单 {{ meta.ticket_id }}</span>
      <el-button type="primary" link @click="goTicket">去工单页查看</el-button>
    </div>
    <div v-if="showOwner && meta.owner?.configured" class="note">
      主题负责人 {{ meta.owner.name }}（{{ meta.owner.topic_name }}），联系方式：{{ meta.owner.contact }}
    </div>
    <div v-if="showOwner && meta.owner && !meta.owner.configured" class="note">该问题未配置主题负责人</div>
  </div>
</template>

<style scoped>
.meta-banner {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 8px;
  margin-top: 12px;
  font-family: var(--font-ui);
}

.hit-pill {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
}

.hit-pill.hit {
  color: #166534;
  background: #dcfce7;
}

.hit-pill.miss {
  color: #9a3412;
  background: #ffedd5;
}

.hit-pill.tool {
  color: #1e3a8a;
  background: #dbeafe;
}

.hit-pill.shot {
  color: #075985;
  background: #e0f2fe;
}

.note {
  font-size: 13px;
  color: var(--color-muted);
}
</style>
