import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { fetchMe, login as loginApi, logout as logoutApi } from "@/api/auth";
import type { LoginPayload, MeResponse } from "@/types";

export const useUserStore = defineStore("user", () => {
  const currentUser = ref<MeResponse | null>(null);
  const bootstrapped = ref(false);

  const isLoggedIn = computed(() => currentUser.value !== null);
  const canManageDocuments = computed(() => Boolean(currentUser.value?.can_manage_documents));

  function clearSession(): void {
    currentUser.value = null;
  }

  async function bootstrap(): Promise<void> {
    try {
      currentUser.value = await fetchMe();
    } catch {
      currentUser.value = null;
    } finally {
      bootstrapped.value = true;
    }
  }

  async function login(payload: LoginPayload): Promise<MeResponse> {
    const user = await loginApi(payload);
    currentUser.value = user;
    return user;
  }

  async function logout(): Promise<void> {
    try {
      await logoutApi();
    } finally {
      clearSession();
    }
  }

  return {
    currentUser,
    bootstrapped,
    isLoggedIn,
    canManageDocuments,
    clearSession,
    bootstrap,
    login,
    logout,
  };
});
