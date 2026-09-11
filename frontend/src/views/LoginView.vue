<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage } from "element-plus";
import BrandMark from "@/components/BrandMark.vue";
import DisclaimerNote from "@/components/DisclaimerNote.vue";
import { useUserStore } from "@/stores/user";
import { describeRequestError } from "@/utils/errors";

interface LoginForm {
  username: string;
  password: string;
}

const router = useRouter();
const route = useRoute();
const userStore = useUserStore();
const formRef = ref<FormInstance>();
const submitting = ref(false);
const accepted = ref(false);
const termsVisible = ref(false);

const form = reactive<LoginForm>({
  username: "",
  password: "",
});

const rules: FormRules<LoginForm> = {
  username: [{ required: true, message: "请输入用户名", trigger: "blur" }],
  password: [{ required: true, message: "请输入密码", trigger: "blur" }],
};

const demoAccounts = [
  { username: "student_demo", label: "学员" },
  { username: "employee_demo", label: "内部员工" },
  { username: "teaching_demo", label: "教学岗" },
];

function fillDemo(username: string): void {
  form.username = username;
  form.password = "demo1234";
}

function agreeTerms(): void {
  accepted.value = true;
  termsVisible.value = false;
}

async function handleSubmit(): Promise<void> {
  if (!accepted.value) {
    ElMessage.warning("请先勾选同意用户须知");
    return;
  }
  const valid = await formRef.value?.validate().catch(() => false);
  if (!valid) {
    return;
  }
  submitting.value = true;
  try {
    await userStore.login({
      username: form.username.trim(),
      password: form.password,
    });
    ElMessage.success("登录成功");
    const redirect = typeof route.query.redirect === "string" ? route.query.redirect : "/qa";
    await router.replace(redirect);
  } catch (error) {
    const described = describeRequestError(error);
    ElMessage.error(`${described.title}：${described.detail}`);
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-brand">
        <BrandMark :size="40" />
        <div>
          <h1>统一知识助手</h1>
          <p class="hint"></p>
        </div>
      </div>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top" @submit.prevent="handleSubmit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" autocomplete="username" @keyup.enter="handleSubmit" />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            @keyup.enter="handleSubmit"
          />
        </el-form-item>
        <div class="terms-row">
          <el-checkbox v-model="accepted">
            我已阅读并同意
            <button type="button" class="terms-link" @click.stop="termsVisible = true">用户须知</button>
          </el-checkbox>
        </div>
        <el-button
          type="primary"
          :loading="submitting"
          :disabled="!accepted"
          class="submit-btn"
          @click="handleSubmit"
        >
          登录
        </el-button>
      </el-form>
      <div class="demo">
        <span>演示账号</span>
        <button v-for="item in demoAccounts" :key="item.username" type="button" class="demo-chip" @click="fillDemo(item.username)">
          {{ item.label }}
        </button>
      </div>
      <DisclaimerNote class="login-disclaimer" />
    </div>
    <el-dialog v-model="termsVisible" title="用户须知" width="480px">
      <div class="terms-body">
        <p>答案由知识库生成，可能不准确。重要事务请向班主任或负责人确认，不要只依据系统回复做决定。</p>
        <p>请勿把内部资料转发到无权查看的渠道。学员只能使用课程空间；请不要尝试套取无权信息。</p>
      </div>
      <template #footer>
        <el-button type="primary" @click="agreeTerms">同意并关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  background: var(--color-page);
}

.login-card {
  width: 420px;
  padding: 32px;
  background: var(--color-card);
  border: 1px solid var(--color-line);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-sm);
}

.login-brand {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  margin-bottom: 24px;
}

h1 {
  margin: 0 0 6px;
  font-family: var(--font-read);
  font-size: 22px;
  font-weight: 700;
  color: var(--color-ink);
}

.hint {
  margin: 0;
  color: var(--color-muted);
  font-size: 13px;
  line-height: 1.6;
}

.submit-btn {
  width: 100%;
  height: 40px;
  margin-top: 4px;
}

.terms-row {
  margin: 4px 0 12px;
}

.terms-row :deep(.el-checkbox) {
  align-items: center;
  white-space: normal;
  height: auto;
}

.terms-link {
  border: 0;
  padding: 0;
  background: none;
  color: var(--color-primary);
  cursor: pointer;
  font: inherit;
}

.terms-link:hover {
  text-decoration: underline;
}

.terms-link:focus-visible {
  outline: 2px solid var(--color-primary);
  outline-offset: 2px;
}

.terms-body p {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--color-ink);
}

.terms-body p:last-child {
  margin-bottom: 0;
}

.demo {
  margin-top: 20px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: var(--color-muted);
  font-size: 13px;
}

.demo-chip {
  border: 1px solid var(--color-line);
  background: var(--color-page);
  color: var(--color-ink);
  border-radius: 999px;
  padding: 4px 10px;
  cursor: pointer;
}

.demo-chip:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-soft);
  color: var(--color-primary);
}

.login-disclaimer {
  margin-top: 16px;
}
</style>
