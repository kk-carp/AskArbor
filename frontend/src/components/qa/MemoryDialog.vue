<script setup lang="ts">
import { computed, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import { deleteMemory, listMemories, listMemoryKeys, upsertMemory } from "@/api/memories";
import type { MemoryItem } from "@/types";
import { describeRequestError } from "@/utils/errors";
import { memoryKeyLabel } from "@/utils/labels";

const props = defineProps<{
  visible: boolean;
}>();

const emit = defineEmits<{
  "update:visible": [value: boolean];
}>();

const DEFAULT_KEYS = [
  "learning_goal",
  "note",
  "preferred_language",
  "preferred_name",
];

const loading = ref(false);
const saving = ref(false);
const keys = ref<string[]>([...DEFAULT_KEYS]);
const items = ref<MemoryItem[]>([]);
const form = reactive({ key: "learning_goal", value: "" });
const VALUE_MAX = 500;

const keyOptions = computed(() =>
  (keys.value || []).map((key) => ({
    value: key,
    label: memoryKeyLabel(key),
  })),
);

const savedItems = computed(() => (Array.isArray(items.value) ? items.value : []));

async function refresh(): Promise<void> {
  loading.value = true;
  try {
    const [keysResp, list] = await Promise.all([listMemoryKeys(), listMemories()]);
    const nextKeys = Array.isArray(keysResp?.keys) ? keysResp.keys.filter(Boolean) : [];
    keys.value = nextKeys.length ? nextKeys : [...DEFAULT_KEYS];
    items.value = Array.isArray(list) ? list : [];
    if (!form.key || !keys.value.includes(form.key)) {
      form.key = keys.value[0] || "learning_goal";
    }
    syncValueFromList();
  } catch (error) {
    ElMessage.error(describeRequestError(error).detail);
    keys.value = [...DEFAULT_KEYS];
    items.value = [];
  } finally {
    loading.value = false;
  }
}

function syncValueFromList(): void {
  const existing = savedItems.value.find((item) => item.key === form.key);
  form.value = typeof existing?.value === "string" ? existing.value : "";
}

watch(
  () => props.visible,
  (visible) => {
    if (visible) {
      void refresh();
    }
  },
);

watch(
  () => form.key,
  () => {
    syncValueFromList();
  },
);

async function handleSave(): Promise<void> {
  const key = (form.key || "").trim();
  const value = (form.value || "").trim();
  if (!key) {
    ElMessage.warning("请选择记忆项");
    return;
  }
  if (!value) {
    ElMessage.warning("记忆内容不能为空");
    return;
  }
  saving.value = true;
  try {
    await upsertMemory(key, value);
    ElMessage.success("已保存，之后新会话提问也会带上");
    await refresh();
  } catch (error) {
    ElMessage.error(describeRequestError(error).detail);
  } finally {
    saving.value = false;
  }
}

async function handleDelete(item: MemoryItem): Promise<void> {
  try {
    await ElMessageBox.confirm(`确认删除「${memoryKeyLabel(item.key)}」？`, "删除确认", {
      type: "warning",
      confirmButtonText: "确定",
      cancelButtonText: "取消",
    });
  } catch {
    return;
  }
  try {
    await deleteMemory(item.key);
    ElMessage.success("已删除");
    await refresh();
  } catch (error) {
    ElMessage.error(describeRequestError(error).detail);
  }
}
</script>

<template>
  <el-dialog
    :model-value="visible"
    title="跨会话记忆"
    width="520px"
    destroy-on-close
    @close="emit('update:visible', false)"
  >
    <p class="hint">
      显式保存的偏好会在之后任意会话的提问中注入；不会写入知识库，也不会出现在来源里。
    </p>
    <div v-loading="loading" class="body">
      <div v-if="savedItems.length" class="saved">
        <div v-for="item in savedItems" :key="item.key" class="saved-row">
          <div class="saved-main">
            <div class="saved-key">{{ memoryKeyLabel(item.key) }}</div>
            <div class="saved-value">{{ item.value }}</div>
          </div>
          <el-button text type="danger" size="small" @click="handleDelete(item)">删除</el-button>
        </div>
      </div>
      <el-form label-position="top" class="editor">
        <el-form-item label="记忆项">
          <el-select v-model="form.key" placeholder="选择要保存的项" style="width: 100%">
            <el-option
              v-for="opt in keyOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="内容">
          <el-input
            :model-value="form.value || ''"
            type="textarea"
            :rows="3"
            :maxlength="VALUE_MAX"
            show-word-limit
            placeholder="例如：想系统学完 RAG 与上下文工程"
            @update:model-value="form.value = String($event ?? '')"
          />
        </el-form-item>
      </el-form>
    </div>
    <template #footer>
      <el-button @click="emit('update:visible', false)">关闭</el-button>
      <el-button type="primary" :loading="saving" @click="handleSave">保存</el-button>
    </template>
  </el-dialog>
</template>

<style scoped>
.hint {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--color-muted);
  line-height: 1.5;
}

.body {
  min-height: 120px;
}

.saved {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--color-line);
}

.saved-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.saved-main {
  flex: 1;
  min-width: 0;
}

.saved-key {
  font-size: 12px;
  color: var(--color-muted);
  margin-bottom: 2px;
}

.saved-value {
  font-size: 14px;
  color: var(--color-ink);
  white-space: pre-wrap;
  word-break: break-word;
}

.editor {
  margin-bottom: 0;
}
</style>
