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
    <el-tag :type="meta.hit ? 'success' : 'warning'" effect="light">
      {{ meta.hit ? "命中知识库" : "未命中知识库" }}
    </el-tag>
    <el-alert
      v-if="showTicket"
      class="meta-alert"
      type="info"
      :closable="false"
      title="已自动创建学员工单"
      :description="`工单号：${meta.ticket_id}`"
    >
      <el-button type="primary" link @click="goTicket">去工单页查看</el-button>
    </el-alert>
    <el-alert
      v-if="showOwner && meta.owner?.configured"
      class="meta-alert"
      type="info"
      :closable="false"
      :title="`主题负责人：${meta.owner.name}（${meta.owner.topic_name}）`"
      :description="`联系方式：${meta.owner.contact}`"
    />
    <el-alert
      v-if="showOwner && meta.owner && !meta.owner.configured"
      class="meta-alert"
      type="info"
      :closable="false"
      title="该问题未配置主题负责人"
    />
  </div>
</template>

<style scoped>
.meta-banner {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 8px 0;
}

.meta-alert {
  margin: 0;
}
</style>
