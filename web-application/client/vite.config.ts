import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { visualizer } from "rollup-plugin-visualizer";

const _dirname = dirname(fileURLToPath(import.meta.url));

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    ...(process.env.ANALYZE
      ? [
          visualizer({
            filename: "dist/stats.html",
            open: true,
            gzipSize: true,
          }),
        ]
      : []),
  ],
  resolve: {
    alias: { "@": resolve(_dirname, "src") },
  },
  server: {
    proxy: {
      "/graphql": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
      "/auth": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
        // /auth is BOTH the API prefix AND the SPA pages /auth/login,
        // /auth/register. Full page loads (Accept: text/html) must be
        // served by the SPA router, not proxied to the API.
        bypass: (req) =>
          req.headers.accept?.includes("text/html") ? "/" : undefined,
      },
      "/api": {
        target: process.env.VITE_API_TARGET ?? "http://localhost:8000",
        changeOrigin: true,
      },
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: [
            "react",
            "react-dom",
            "react-router",
            "@tanstack/react-query",
          ],
          ui: [
            "@base-ui/react",
            "class-variance-authority",
            "clsx",
            "tailwind-merge",
          ],
          icons: ["lucide-react"],
          data: ["urql", "@urql/core", "graphql"],
        },
      },
    },
  },
});
