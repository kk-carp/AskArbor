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

function goTicket(): void {
  if (!props.meta?.ticket_id) {
    return;
  }
  void router.push({ name: "work-orders", query: { ticket_id: props.meta.ticket_id } });
}
</script>

<template>
  <div v-if="meta" class="meta-banner">
    <span class="hit-pill" :class="meta.hit ? 'hit' : 'miss'">
      {{ meta.hit ? "已命中知识库" : "未命中知识库" }}
    </span>
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
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
}

.hit-pill.hit {
  color: #166534;
  background: #f0fdf4;
}

.hit-pill.miss {
  color: #9a3412;
  background: #fff7ed;
}

.note {
  font-size: 13px;
  color: var(--color-muted);
  line-height: 1.6;
}
</style>
