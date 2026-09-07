<script setup lang="ts">
import { reactive, ref } from "vue";
import type { FormInstance, FormRules, UploadFile } from "element-plus";
import { ElMessage } from "element-plus";

interface CodePackForm {
  file: File | null;
}

defineProps<{
  visible: boolean;
  submitting: boolean;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
  submit: [file: File];
}>();

const formRef = ref<FormInstance>();
const form = reactive<CodePackForm>({
  file: null,
});

const rules: FormRules<CodePackForm> = {
  file: [
    {
      validator: (_rule, value: File | null, callback) => {
        if (!value) {
          callback(new Error("请选择 zip 文件"));
          return;
        }
        callback();
      },
      trigger: "change",
    },
  ],
};

function handleFileChange(uploadFile: UploadFile): void {
  const file = uploadFile.raw ?? null;
  if (!file) {
    form.file = null;
    return;
  }
  if (!file.name.toLowerCase().endsWith(".zip")) {
    ElMessage.error("仅支持 zip 课程代码包");
    form.file = null;
    return;
  }
  form.file = file;
}

function handleRemove(): void {
  form.file = null;
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid || !form.file) {
    return;
  }
  emit("submit", form.file);
}

function handleClose(): void {
  form.file = null;
  formRef.value?.resetFields();
  emit("update:visible", false);
}
</script>

<template>
  <el-dialog :model-value="visible" title="上传课程代码包" width="480px" @close="handleClose">
    <p class="hint">空间由服务端定为课程空间 student，不会写入内部空间。</p>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="zip 包" prop="file">
        <el-upload
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-remove="handleRemove"
          accept=".zip"
        >
          <el-button>选择 zip</el-button>
        </el-upload>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">上传入库</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  margin: 0 0 12px;
  color: var(--color-muted);
  font-size: 13px;
}
</style>
