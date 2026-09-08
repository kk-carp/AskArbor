<script setup lang="ts">
import { computed, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ChatDotRound, Expand, FolderOpened, Fold, Reading, Tickets, UserFilled } from "@element-plus/icons-vue";
import { ElMessage } from "element-plus";
import BrandMark from "@/components/BrandMark.vue";
import { useUserStore } from "@/stores/user";
import { displayRole, spaceLabel } from "@/utils/labels";

const COLLAPSE_STORAGE_KEY = "fde-sidebar-collapsed";

const route = useRoute();
const router = useRouter();
const userStore = useUserStore();

const user = computed(() => userStore.currentUser);
const canManage = computed(() => userStore.canManageDocuments);
const canUseCompanion = computed(() => userStore.canUseCompanion);
const collapsed = ref(readCollapsed());
const asideWidth = computed(() => (collapsed.value ? "72px" : "228px"));
const isQa = computed(() => route.name === "qa");

const menuItems = computed(() => {
  const items = [{ index: "/qa", title: "问答", icon: ChatDotRound }];
  if (canUseCompanion.value) {
    items.push({ index: "/study-path", title: "学习路径", icon: Reading });
  }
  items.push({ index: "/work-orders", title: "工单", icon: Tickets });
  if (canManage.value) {
    items.push({ index: "/knowledge", title: "文档管理", icon: FolderOpened });
    items.push({ index: "/topic-owners", title: "主题负责人", icon: UserFilled });
  }
  return items;
});

function readCollapsed(): boolean {
  try {
    return localStorage.getItem(COLLAPSE_STORAGE_KEY) === "1";
  } catch {
    return false;
  }
}

function toggleCollapsed(): void {
  collapsed.value = !collapsed.value;
  try {
    localStorage.setItem(COLLAPSE_STORAGE_KEY, collapsed.value ? "1" : "0");
  } catch {
    /* ignore quota / private mode */
  }
}

async function handleLogout(): Promise<void> {
  await userStore.logout();
  ElMessage.success("已退出");
  await router.push({ name: "login" });
}
</script>

<template>
  <el-container class="app-shell">
    <el-aside :width="asideWidth" class="app-aside">
      <div class="brand" :class="{ collapsed }">
        <BrandMark :size="collapsed ? 28 : 32" />
        <span v-if="!collapsed" class="brand-text">统一知识助手</span>
      </div>
      <el-menu
        :router="true"
        :collapse="collapsed"
        :default-active="route.path"
        class="aside-menu"
        background-color="#ffffff"
        text-color="#64748B"
        active-text-color="#2563EB"
      >
        <el-menu-item v-for="item in menuItems" :key="item.index" :index="item.index">
          <el-icon>
            <component :is="item.icon" />
          </el-icon>
          <template #title>
            <span>{{ item.title }}</span>
          </template>
        </el-menu-item>
      </el-menu>
      <button
        type="button"
        class="aside-toggle"
        :title="collapsed ? '展开侧边栏' : '收起侧边栏'"
        :aria-label="collapsed ? '展开侧边栏' : '收起侧边栏'"
        :aria-expanded="!collapsed"
        @click="toggleCollapsed"
      >
        <el-icon>
          <Expand v-if="collapsed" />
          <Fold v-else />
        </el-icon>
        <span v-if="!collapsed">收起菜单</span>
      </button>
    </el-aside>
    <el-container class="app-body">
      <el-header class="app-header" height="56px">
        <div class="header-title">{{ route.meta.title }}</div>
        <div v-if="user" class="header-user">
          <span class="user-name">{{ user.username }}</span>
          <el-tag size="small" effect="plain" type="primary">{{ displayRole(user) }}</el-tag>
          <el-tag v-for="space in user.allowed_spaces" :key="space" size="small" effect="plain">
            {{ spaceLabel(space) }}
          </el-tag>
          <el-button type="primary" link @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="app-main" :class="{ 'is-qa': isQa }">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.app-shell {
  height: 100%;
  background: var(--color-page);
}

.app-aside {
  display: flex;
  flex-direction: column;
  overflow: hidden;
  background: var(--color-card);
  border-right: 1px solid var(--color-line);
  transition: width 0.2s ease;
}

.brand {
  height: 56px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 16px;
  flex-shrink: 0;
}

.brand.collapsed {
  justify-content: center;
  padding: 0;
}

.brand-text {
  font-family: var(--font-read);
  font-weight: 700;
  font-size: 16px;
  color: var(--color-ink);
  white-space: nowrap;
}

.aside-menu {
  flex: 1;
  border-right: none;
  overflow: auto;
  padding-top: 8px;
}

.aside-menu:not(.el-menu--collapse) :deep(.el-menu-item) {
  margin: 2px 10px;
  width: calc(100% - 20px);
  border-radius: var(--radius-sm);
  height: 42px;
}

.aside-menu :deep(.el-menu-item:hover) {
  background: var(--color-page);
}

.aside-menu :deep(.el-menu-item.is-active) {
  background: var(--color-primary-soft);
  font-weight: 600;
}

.aside-toggle {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 48px;
  width: 100%;
  flex-shrink: 0;
  border: none;
  border-top: 1px solid var(--color-line);
  background: transparent;
  color: var(--color-muted);
  cursor: pointer;
}

.aside-toggle:hover {
  color: var(--color-ink);
  background: var(--color-page);
}

.app-body {
  min-width: 0;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--color-card);
  border-bottom: 1px solid var(--color-line);
}

.header-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-ink);
}

.header-user {
  display: flex;
  align-items: center;
  gap: 8px;
}

.user-name {
  font-size: 13px;
  color: var(--color-muted);
}

.app-main {
  padding: 20px 24px 24px;
  overflow: auto;
  background: var(--color-page);
}

.app-main.is-qa {
  padding: 12px;
  overflow: hidden;
  background: var(--color-page);
}
</style>
