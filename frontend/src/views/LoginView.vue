<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage } from "element-plus";
import BrandMark from "@/components/BrandMark.vue";
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

async function handleSubmit(): Promise<void> {
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
        <el-button type="primary" :loading="submitting" class="submit-btn" @click="handleSubmit">登录</el-button>
      </el-form>
      <div class="demo">
        <span>演示账号</span>
        <button v-for="item in demoAccounts" :key="item.username" type="button" class="demo-chip" @click="fillDemo(item.username)">
          {{ item.label }}
        </button>
      </div>
    </div>
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
</style>
