<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import type { FormInstance, FormRules } from "element-plus";
import type { TicketItem } from "@/types";

interface ReplyForm {
  reply: string;
}

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
  ticket: TicketItem | null;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
  submit: [reply: string];
}>();

const formRef = ref<FormInstance>();
const form = reactive<ReplyForm>({ reply: "" });
const rules: FormRules<ReplyForm> = {
  reply: [{ required: true, message: "回复不能为空", trigger: "blur" }],
};

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      form.reply = "";
      formRef.value?.clearValidate();
    }
  },
);

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  emit("submit", form.reply.trim());
}
</script>

<template>
  <el-dialog :model-value="visible" title="回复工单" width="520px" @close="emit('update:visible', false)">
    <p v-if="ticket" class="question">问题：{{ ticket.question }}</p>
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="回复内容" prop="reply">
        <el-input v-model="form.reply" type="textarea" :rows="4" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">提交回复</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.question {
  margin: 0 0 12px;
  color: var(--color-ink);
}

.hint {
  margin: 0;
  color: var(--color-muted);
  font-size: 12px;
}
</style>
