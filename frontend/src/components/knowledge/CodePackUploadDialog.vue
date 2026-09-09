<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import type { FormInstance, FormRules, UploadFile, UploadInstance, UploadUserFile } from "element-plus";
import { ElMessage } from "element-plus";

interface CodePackForm {
  file: File | null;
}

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
  submit: [file: File];
}>();

const formRef = ref<FormInstance>();
const uploadRef = ref<UploadInstance>();
const fileList = ref<UploadUserFile[]>([]);
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

function resetUploadState(): void {
  form.file = null;
  fileList.value = [];
  uploadRef.value?.clearFiles();
  formRef.value?.clearValidate();
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      resetUploadState();
    }
  },
);

function handleFileChange(uploadFile: UploadFile, files: UploadUserFile[]): void {
  const file = uploadFile.raw ?? null;
  if (!file) {
    form.file = null;
    fileList.value = files;
    return;
  }
  if (!file.name.toLowerCase().endsWith(".zip")) {
    ElMessage.error("仅支持 zip 课程代码包");
    form.file = null;
    fileList.value = [];
    uploadRef.value?.clearFiles();
    return;
  }
  form.file = file;
  fileList.value = files.slice(-1);
}

function handleRemove(): void {
  form.file = null;
  fileList.value = [];
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid || !form.file) {
    return;
  }
  emit("submit", form.file);
}

function handleClose(): void {
  resetUploadState();
  emit("update:visible", false);
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="上传课程代码包"
    width="480px"
    destroy-on-close
    @close="handleClose"
  >
    <p class="hint">空间由服务端定为课程空间 student，不会写入内部空间。</p>
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="zip 包" prop="file">
        <el-upload
          ref="uploadRef"
          v-model:file-list="fileList"
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
