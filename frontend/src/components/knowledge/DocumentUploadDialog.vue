<script setup lang="ts">
import { reactive, ref } from "vue";
import type { FormInstance, FormRules, UploadFile } from "element-plus";
import { ElMessage } from "element-plus";
import type { SpaceId } from "@/types";

interface UploadForm {
  space: SpaceId;
  file: File | null;
}

defineProps<{
  visible: boolean;
  submitting: boolean;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
  submit: [payload: { space: SpaceId; file: File }];
}>();

const formRef = ref<FormInstance>();
const form = reactive<UploadForm>({
  space: "student",
  file: null,
});

const rules: FormRules<UploadForm> = {
  space: [{ required: true, message: "请选择知识空间", trigger: "change" }],
  file: [
    {
      validator: (_rule, value: File | null, callback) => {
        if (!value) {
          callback(new Error("请选择文件"));
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
  const allowed = [".md", ".txt", ".pdf", ".docx"];
  const name = file.name.toLowerCase();
  const ext = name.slice(name.lastIndexOf("."));
  if (!allowed.includes(ext)) {
    ElMessage.error("仅支持 md / txt / pdf / docx");
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
  emit("submit", { space: form.space, file: form.file });
}

function handleClose(): void {
  form.space = "student";
  form.file = null;
  formRef.value?.resetFields();
  emit("update:visible", false);
}
</script>

<template>
  <el-dialog :model-value="visible" title="上传文档" width="480px" @close="handleClose">
    <el-form ref="formRef" :model="form" :rules="rules" label-width="96px">
      <el-form-item label="知识空间" prop="space">
        <el-select v-model="form.space" style="width: 100%">
          <el-option label="课程空间 student" value="student" />
          <el-option label="内部空间 company" value="company" />
        </el-select>
      </el-form-item>
      <el-form-item label="文件" prop="file">
        <el-upload
          :auto-upload="false"
          :limit="1"
          :on-change="handleFileChange"
          :on-remove="handleRemove"
          accept=".md,.txt,.pdf,.docx"
        >
          <el-button>选择文件</el-button>
        </el-upload>
      </el-form-item>
    </el-form>
    <template #footer>
      <el-button @click="handleClose">取消</el-button>
      <el-button type="primary" :loading="submitting" @click="handleSubmit">上传入库</el-button>
    </template>
  </el-dialog>
</template>
