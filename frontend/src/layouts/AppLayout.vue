<script setup lang="ts">
import { computed } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ChatDotRound, FolderOpened, Tickets, UserFilled } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import { useUserStore } from "@/stores/user";
import { displayRole, spaceLabel } from "@/utils/labels";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const user = computed(() => userStore.currentUser);
const canManage = computed(() => userStore.canManageDocuments);

const menuItems = computed(() => {
  const items = [
    { index: "/qa", title: "问答", icon: ChatDotRound },
    { index: "/work-orders", title: "工单", icon: Tickets },
  ];
  if (canManage.value) {
    items.push({ index: "/knowledge", title: "文档管理", icon: FolderOpened });
    items.push({ index: "/topic-owners", title: "主题负责人", icon: UserFilled });
  }
  return items;
});

async function handleLogout(): Promise<void> {
  await userStore.logout();
  ElMessage.success("已退出");
  await router.push({ name: "login" });
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside width="220px" class="app-aside">
      <div class="brand">统一知识助手</div>
      <el-menu :router="true" :default-active="route.path" background-color="#1f2a37" text-color="#d7dee8" active-text-color="#ffffff">
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <span>{{ item.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="app-header">
        <div class="header-title">{{ route.meta.title }}</div>
        <div v-if="user" class="header-user">
          <span>{{ user.username }}</span>
          <el-tag size="small" type="info">{{ displayRole(user) }}</el-tag>
          <el-tag v-for="space in user.allowed_spaces" :key="space" size="small">
            {{ spaceLabel(space) }}
          </el-tag>
          <el-button type="primary" link @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-shell {
  height: 100%;
}

.app-aside {
  background: #1f2a37;
  color: #fff;
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  padding: 0 20px;
  font-weight: 700;
  letter-spacing: 0.04em;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: #fff;
  border-bottom: 1px solid #ebeef5;
}

.header-title {
  font-size: 16px;
  font-weight: 600;
}

.header-user {
  display: flex;
  align-items: center;
  gap: 8px;
}

.app-main {
  padding: 16px 20px 24px;
}
</style>
