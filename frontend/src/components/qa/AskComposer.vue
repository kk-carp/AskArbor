<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { Picture, Top } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";

interface AskForm {
  question: string;
}

const props = defineProps<{
  loading: boolean;
}>();

const emit = defineEmits<{
  submit: [payload: { question: string; image: File | null }];
}>();

const form = reactive<AskForm>({ question: "" });
const imageFile = ref<File | null>(null);
const imagePreview = ref<string | null>(null);
const fileInput = ref<HTMLInputElement | null>(null);

const canSubmit = computed(
  () => (Boolean(form.question.trim()) || imageFile.value !== null) && !props.loading,
);

function pickImage(): void {
  fileInput.value?.click();
}

function onFileChange(event: Event): void {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0] || null;
  input.value = "";
  if (!file) {
    return;
  }
  if (!file.type.startsWith("image/")) {
    ElMessage.error("请选择图片文件");
    return;
  }
  if (file.size > 10 * 1024 * 1024) {
    ElMessage.error("图片过大（上限 10MB）");
    return;
  }
  imageFile.value = file;
  if (imagePreview.value) {
    URL.revokeObjectURL(imagePreview.value);
  }
  imagePreview.value = URL.createObjectURL(file);
}

function clearImage(): void {
  imageFile.value = null;
  if (imagePreview.value) {
    URL.revokeObjectURL(imagePreview.value);
    imagePreview.value = null;
  }
}

function handleSubmit(): void {
  if (!canSubmit.value) {
    return;
  }
  const question = form.question.trim();
  const image = imageFile.value;
  form.question = "";
  imageFile.value = null;
  if (imagePreview.value) {
    URL.revokeObjectURL(imagePreview.value);
    imagePreview.value = null;
  }
  emit("submit", { question, image });
}

function resetQuestion(): void {
  form.question = "";
  clearImage();
}

defineExpose({ resetQuestion });
</script>

<template>
  <form class="composer" @submit.prevent="handleSubmit">
    <div class="composer-box">
      <div v-if="imagePreview" class="image-preview">
        <img :src="imagePreview" alt="待识别截图" />
        <el-button text type="danger" size="small" :disabled="loading" @click="clearImage">移除</el-button>
      </div>
      <el-input
        v-model="form.question"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 6 }"
        maxlength="2000"
        resize="none"
        placeholder="输入问题，或上传代码/公式截图；Enter 发送，Shift + Enter 换行"
        :disabled="loading"
        @keydown.enter.exact.prevent="handleSubmit"
      />
      <div class="composer-bar">
        <input
          ref="fileInput"
          class="hidden-input"
          type="file"
          accept="image/png,image/jpeg,image/webp,image/gif"
          @change="onFileChange"
        />
        <el-button text :disabled="loading" @click="pickImage">
          <el-icon><Picture /></el-icon>
          截图
        </el-button>
        <span class="hint"></span>
        <span class="count">{{ form.question.length }} / 2000</span>
        <button
          type="button"
          class="send-btn"
          :disabled="!canSubmit"
          aria-label="提问"
          @click="handleSubmit"
        >
          <span v-if="loading" class="send-spinner" aria-hidden="true" />
          <el-icon v-else><Top /></el-icon>
        </button>
      </div>
    </div>
  </form>
</template>

<style scoped>
.composer {
  width: min(760px, 100%);
  margin: 0 auto;
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

.image-preview {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin-bottom: 8px;
}

.image-preview img {
  max-height: 96px;
  max-width: 220px;
  border-radius: 8px;
  border: 1px solid var(--color-line);
  object-fit: contain;
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

.hidden-input {
  display: none;
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

.send-btn {
  width: 36px;
  height: 36px;
  border: none;
  border-radius: 50%;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--color-primary);
  color: #fff;
  cursor: pointer;
  flex-shrink: 0;
}

.send-btn:disabled {
  opacity: 0.45;
  cursor: not-allowed;
}

.send-btn .el-icon {
  font-size: 16px;
}

.send-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.35);
  border-top-color: #fff;
  border-radius: 50%;
  animation: send-spin 0.7s linear infinite;
}

@keyframes send-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
