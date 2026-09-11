import { fileURLToPath, URL } from "node:url";
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import type { IncomingMessage } from "node:http";

const apiTarget = "http://127.0.0.1:8000";

function isApiGet(url: string): boolean {
  return (
    url === "/me" ||
    url === "/health" ||
    url === "/metrics" ||
    url === "/documents" ||
    (url.startsWith("/documents/") && url.endsWith("/file")) ||
    url === "/conversations" ||
    url.startsWith("/conversations/") ||
    url === "/tickets" ||
    url === "/topic_owners" ||
    url === "/advanced-resources/tools" ||
    url.startsWith("/advanced-resources/")
  );
}

function isApiWrite(url: string): boolean {
  return (
    url === "/login" ||
    url === "/logout" ||
    url === "/ask" ||
    url === "/ask/stream" ||
    url === "/ocr" ||
    url === "/documents" ||
    url === "/documents/batch-offline" ||
    url === "/documents/batch-delete" ||
    url.startsWith("/documents/") ||
    url === "/code-ingest" ||
    url === "/tickets" ||
    url.startsWith("/tickets/") ||
    url === "/topic_owners" ||
    url === "/advanced-resources/run" ||
    url === "/advanced-resources/plan" ||
    url.startsWith("/advanced-resources/")
  );
}

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    host: "127.0.0.1",
    proxy: {
      "^/(login|logout|me|ask|ocr|documents|code-ingest|conversations|tickets|topic_owners|advanced-resources|health|metrics)(/.*)?$": {
        target: apiTarget,
        changeOrigin: true,
        bypass(req: IncomingMessage) {
          const url = (req.url || "").split("?")[0];
          const method = (req.method || "GET").toUpperCase();
          if (method === "GET" || method === "HEAD") {
            return isApiGet(url) ? undefined : "/index.html";
          }
          return isApiWrite(url) ? undefined : "/index.html";
        },
      },
    },
  },
});
