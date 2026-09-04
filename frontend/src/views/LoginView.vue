<script setup lang="ts">
import { reactive, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import type { FormInstance, FormRules } from "element-plus";
import { ElMessage } from "element-plus";
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
    <el-card class="login-card" shadow="hover">
      <h1>统一知识助手</h1>
      <p class="hint">可检索空间由服务端按账号成员关系计算，页面不能切换空间。</p>
      <el-form ref="formRef" :model="form" :rules="rules" label-position="top">
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
        <span>演示账号：</span>
        <el-button v-for="item in demoAccounts" :key="item.username" size="small" @click="fillDemo(item.username)">
          {{ item.label }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(180deg, #eef3f8 0%, #f5f7fa 100%);
}

.login-card {
  width: 420px;
}

h1 {
  margin: 0 0 8px;
  font-size: 22px;
}

.hint {
  margin: 0 0 16px;
  color: #909399;
  font-size: 13px;
}

.submit-btn {
  width: 100%;
}

.demo {
  margin-top: 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  color: #606266;
  font-size: 13px;
}
</style>
