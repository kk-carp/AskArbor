<script setup lang="ts">
import { reactive, ref } from "vue";
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
  <el-form ref="formRef" :model="form" :rules="rules">
    <el-form-item prop="question">
      <el-input
        v-model="form.question"
        type="textarea"
        :rows="3"
        maxlength="2000"
        show-word-limit
        placeholder="输入问题。不要在页面上选择空间；可检索范围由登录账号决定。"
      />
    </el-form-item>
    <el-form-item>
      <el-button type="primary" :loading="loading" @click="handleSubmit">提问</el-button>
    </el-form-item>
  </el-form>
</template>
