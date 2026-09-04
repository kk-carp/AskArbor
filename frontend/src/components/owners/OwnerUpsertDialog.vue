<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import type { FormInstance, FormRules } from "element-plus";
import type { TopicOwnerItem, TopicOwnerUpsertPayload } from "@/types";

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
  editing: TopicOwnerItem | null;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
  submit: [payload: TopicOwnerUpsertPayload];
}>();

const formRef = ref<FormInstance>();
const form = reactive<TopicOwnerUpsertPayload>({
  topic_key: "",
  topic_name: "",
  keywords: "",
  name: "",
  contact: "",
});

const rules: FormRules<TopicOwnerUpsertPayload> = {
  topic_key: [
    { required: true, message: "主题 key 不能为空", trigger: "blur" },
    { max: 64, message: "不超过 64 个字符", trigger: "blur" },
  ],
  topic_name: [
    { required: true, message: "主题名称不能为空", trigger: "blur" },
    { max: 128, message: "不超过 128 个字符", trigger: "blur" },
  ],
  name: [
    { required: true, message: "负责人姓名不能为空", trigger: "blur" },
    { max: 64, message: "不超过 64 个字符", trigger: "blur" },
  ],
  contact: [
    { required: true, message: "联系方式不能为空", trigger: "blur" },
    { max: 255, message: "不超过 255 个字符", trigger: "blur" },
  ],
};

watch(
  () => props.visible,
  (visible) => {
    if (!visible) {
      return;
    }
    form.topic_key = props.editing?.topic_key ?? "";
    form.topic_name = props.editing?.topic_name ?? "";
    form.keywords = props.editing?.keywords ?? "";
    form.name = props.editing?.name ?? "";
    form.contact = props.editing?.contact ?? "";
  },
);

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  emit("submit", { ...form });
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    :title="editing ? '更新主题负责人' : '新增主题负责人'"
    width="520px"
    @close="emit('update:visible', false)"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="108px">
      <el-form-item label="主题 key" prop="topic_key">
        <el-input v-model="form.topic_key" :disabled="Boolean(editing)" placeholder="leave" />
      </el-form-item>
      <el-form-item label="主题名称" prop="topic_name">
        <el-input v-model="form.topic_name" placeholder="请假休假" />
      </el-form-item>
      <el-form-item label="关键词" prop="keywords">
        <el-input v-model="form.keywords" placeholder="请假,休假,年假" />
      </el-form-item>
      <el-form-item label="负责人姓名" prop="name">
        <el-input v-model="form.name" />
      </el-form-item>
      <el-form-item label="联系方式" prop="contact">
        <el-input v-model="form.contact" placeholder="仅使用表单提交值，不经模型生成" />
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="emit('update:visible', false)">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">保存</el-button>
    </template>
  </el-dialog>
</template>
