<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import type { FormInstance, FormRules } from "element-plus";

interface CreateForm {
  question: string;
}

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
  submit: [question: string];
}>();

const formRef = ref<FormInstance>();
const form = reactive<CreateForm>({ question: "" });
const rules: FormRules<CreateForm> = {
  question: [{ required: true, message: "问题不能为空", trigger: "blur" }],
};

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      form.question = "";
      formRef.value?.clearValidate();
    }
  },
);

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  emit("submit", form.question.trim());
}
</script>

<template>
  <el-dialog :model-value="visible" title="显式转人工" width="480px" @close="emit('update:visible', false)">
    <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
      <el-form-item label="问题" prop="question">
        <el-input v-model="form.question" type="textarea" :rows="4" placeholder="知识库未覆盖时，提交给班主任" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">创建工单</el-button>
    </template>
  </el-dialog>
</template>
