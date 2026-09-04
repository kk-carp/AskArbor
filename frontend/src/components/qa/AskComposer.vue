<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Top } from "@element-plus/icons-vue";
import type { FormInstance, FormRules } from "element-plus";

interface AskForm {
  question: string;
}

const props = defineProps<{
  loading: boolean;
}>();

const emit = defineEmits<{
  submit: [question: string];
}>();

const formRef = ref<FormInstance>();
const form = reactive<AskForm>({ question: "" });
const rules: FormRules<AskForm> = {
  question: [
    {
      validator: (_rule, value: string, callback) => {
        if (!value || !value.trim()) {
          callback(new Error("问题不能为空"));
          return;
        }
        callback();
      },
      trigger: "blur",
    },
  ],
};

const canSubmit = computed(() => Boolean(form.question.trim()) && !props.loading);

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid || props.loading) {
    return;
  }
  emit("submit", form.question.trim());
}

function resetQuestion(): void {
  form.question = "";
  formRef.value?.clearValidate();
}

defineExpose({ resetQuestion });
</script>

<template>
  <el-form ref="formRef" :model="form" :rules="rules" class="composer" @submit.prevent="handleSubmit">
    <el-form-item prop="question" class="composer-field">
      <div class="composer-box">
        <el-input
          v-model="form.question"
          type="textarea"
          :autosize="{ minRows: 1, maxRows: 6 }"
          maxlength="2000"
          resize="none"
          placeholder="输入问题，Enter 发送，Shift + Enter 换行"
          :disabled="loading"
          @keydown.enter.exact.prevent="handleSubmit"
        />
        <div class="composer-bar">
          <span class="hint"></span>
          <span class="count">{{ form.question.length }} / 2000</span>
          <el-button
            type="primary"
            circle
            :loading="loading"
            :disabled="!canSubmit"
            aria-label="提问"
            @click="handleSubmit"
          >
            <el-icon v-if="!loading"><Top /></el-icon>
          </el-button>
        </div>
      </div>
    </el-form-item>
  </el-form>
</template>

<style scoped>
.composer {
  width: min(760px, 100%);
  margin: 0 auto;
}

.composer-field {
  margin-bottom: 0;
}

.composer-field :deep(.el-form-item__content) {
  width: 100%;
  display: block;
}

.composer-box {
  width: 100%;
  border: 1px solid var(--color-line);
  border-radius: 18px;
  background: var(--color-card);
  box-shadow: var(--shadow-sm);
  padding: 10px 12px 8px;
}

.composer-box:hover {
  border-color: #cbd5e1;
}

.composer-box:focus-within {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}

.composer-box :deep(.el-textarea__inner) {
  box-shadow: none;
  border: none;
  padding: 4px 4px 8px;
  background: transparent;
  color: var(--color-ink);
}

.composer-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.hint {
  flex: 1;
  font-size: 12px;
  color: var(--color-muted);
}

.count {
  font-size: 12px;
  color: var(--color-muted);
}

.composer-bar :deep(.el-button.is-circle) {
  width: 36px;
  height: 36px;
}
</style>
