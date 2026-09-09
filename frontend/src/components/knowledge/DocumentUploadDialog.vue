<script setup lang="ts">
import { reactive, ref, watch } from "vue";
import type { FormInstance, FormRules, UploadFile, UploadInstance, UploadUserFile } from "element-plus";
import { ElMessage } from "element-plus";
import type { SpaceId } from "@/types";

interface UploadForm {
  space: SpaceId;
  files: File[];
}

const props = defineProps<{
  visible: boolean;
  submitting: boolean;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
  submit: [payload: { space: SpaceId; files: File[] }];
}>();

const formRef = ref<FormInstance>();
const uploadRef = ref<UploadInstance>();
const fileList = ref<UploadUserFile[]>([]);
const form = reactive<UploadForm>({
  space: "student",
  files: [],
});

const rules: FormRules<UploadForm> = {
  space: [{ required: true, message: "请选择知识空间", trigger: "change" }],
  files: [
    {
      validator: (_rule, value: File[], callback) => {
        if (!value.length) {
          callback(new Error("请选择文件"));
          return;
        }
        callback();
      },
      trigger: "change",
    },
  ],
};

const allowedExt = [".md", ".txt", ".pdf", ".docx", ".pptx"];

function resetUploadState(): void {
  form.space = "student";
  form.files = [];
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

function isAllowed(file: File): boolean {
  const name = file.name.toLowerCase();
  const ext = name.slice(name.lastIndexOf("."));
  return allowedExt.includes(ext);
}

function syncFiles(files: UploadUserFile[]): void {
  const nextList: UploadUserFile[] = [];
  const nextFiles: File[] = [];
  for (const item of files) {
    const raw = item.raw;
    if (!raw) {
      continue;
    }
    if (!isAllowed(raw)) {
      ElMessage.error(`${raw.name}：仅支持 md / txt / pdf / docx / pptx`);
      continue;
    }
    nextList.push(item);
    nextFiles.push(raw);
  }
  fileList.value = nextList;
  form.files = nextFiles;
}

function handleFileChange(_uploadFile: UploadFile, files: UploadUserFile[]): void {
  syncFiles(files);
}

function handleRemove(_uploadFile: UploadFile, files: UploadUserFile[]): void {
  syncFiles(files);
}

async function handleSubmit(): Promise<void> {
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid || !form.files.length) {
    return;
  }
  emit("submit", { space: form.space, files: [...form.files] });
}

function handleClose(): void {
  resetUploadState();
  emit("update:visible", false);
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="上传文档"
    width="480px"
    destroy-on-close
    @close="handleClose"
  >
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="知识空间" prop="space">
        <el-select v-model="form.space" style="width: 100%">
          <el-option label="课程空间 student" value="student" />
          <el-option label="内部空间 company" value="company" />
        </el-select>
      </el-form-item>
      <el-form-item label="文件" prop="files">
        <el-upload
          ref="uploadRef"
          v-model:file-list="fileList"
          :auto-upload="false"
          multiple
          :on-change="handleFileChange"
          :on-remove="handleRemove"
          accept=".md,.txt,.pdf,.docx,.pptx"
        >
          <el-button>选择文件</el-button>
          <template #tip>
            <div class="el-upload__tip">支持 md / txt / pdf / docx / pptx，单个不超过 50 MB</div>
          </template>
        </el-upload>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">上传入库</el-button>
    </template>
  </el-dialog>
</template>
