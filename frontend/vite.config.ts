import { defineConfig } from "vite";

export default defineConfig({
  server: {
    host: "0.0.0.0",
    port: 7861,
    proxy: {
      "/v1": {
        target: process.env.API_URL || "http://localhost:8882",
        changeOrigin: true,
      },
    },
  },
  preview: {
    host: "0.0.0.0",
    port: 7861,
    proxy: {
      "/v1": {
        target: process.env.API_URL || "http://localhost:8882",
        changeOrigin: true,
      },
    },
  },
});
