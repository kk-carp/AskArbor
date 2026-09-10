import { createRouter, createWebHistory } from "vue-router";
import { useUserStore } from "@/stores/user";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/views/LoginView.vue"),
      meta: { public: true, title: "登录" },
    },
    {
      path: "/",
      component: () => import("@/layouts/AppLayout.vue"),
      redirect: "/qa",
      children: [
        {
          path: "qa",
          name: "qa",
          component: () => import("@/views/QaView.vue"),
          meta: { title: "问答" },
        },
        {
          path: "advanced-resources",
          name: "advanced-resources",
          component: () => import("@/views/AdvancedResourcesView.vue"),
          meta: { title: "进阶资料推荐", requireCompanion: true },
        },
        {
          path: "knowledge",
          name: "knowledge",
          component: () => import("@/views/KnowledgeView.vue"),
          meta: { title: "文档管理", requireManage: true },
        },
        {
          path: "work-orders",
          name: "work-orders",
          component: () => import("@/views/TicketsView.vue"),
          meta: { title: "工单" },
        },
        {
          path: "topic-owners",
          name: "topic-owners",
          component: () => import("@/views/TopicOwnersView.vue"),
          meta: { title: "主题负责人", requireManage: true },
        },
        {
          path: "metrics",
          name: "metrics",
          component: () => import("@/views/MetricsView.vue"),
          meta: { title: "运行概况", requireTeaching: true },
        },
      ],
    },
    { path: "/:pathMatch(.*)*", redirect: "/qa" },
  ],
});

router.beforeEach(async (to) => {
  const userStore = useUserStore();
  if (!userStore.bootstrapped) {
    await userStore.bootstrap();
  }
  if (to.meta.public) {
    if (userStore.isLoggedIn && to.name === "login") {
      return { name: "qa" };
    }
    return true;
  }
  if (!userStore.isLoggedIn) {
    return { name: "login", query: { redirect: to.fullPath } };
  }
  if (to.meta.requireManage && !userStore.canManageDocuments) {
    return { name: "qa" };
  }
  if (to.meta.requireCompanion && !userStore.canUseCompanion) {
    return { name: "qa" };
  }
  if (to.meta.requireTeaching && !userStore.canViewMetrics) {
    return { name: "qa" };
  }
  return true;
});

export default router;
