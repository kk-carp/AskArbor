import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import zhCn from "element-plus/es/locale/lang/zh-cn";
import * as ElementPlusIconsVue from "@element-plus/icons-vue";
import "element-plus/dist/index.css";
import App from "./App.vue";
import router from "./router";
import { setUnauthorizedHandler } from "@/api/http";
import { useUserStore } from "@/stores/user";
import "./styles/global.css";

const app = createApp(App);
const pinia = createPinia();

app.use(pinia);
app.use(router);
app.use(ElementPlus, { locale: zhCn });

for (const [name, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(name, component);
}

const userStore = useUserStore();
setUnauthorizedHandler(() => {
  userStore.clearSession();
  if (router.currentRoute.value.name !== "login") {
    void router.push({ name: "login" });
  }
});

app.mount("#app");
