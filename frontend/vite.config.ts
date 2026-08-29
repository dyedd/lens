import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react-swc";
import { defineConfig } from "vite";

// Single source of truth for the dev API port; `lens dev` exports this variable.
const backendTarget = process.env.LENS_DEV_BACKEND ?? "http://127.0.0.1:18080";

export default defineConfig({
  build: {
    // The backend serves the build from inside its own package, so `pnpm build`
    // followed by `lens serve` needs no extra flags or copying.
    outDir: "../backend/app/frontend",
    emptyOutDir: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    // Bound explicitly to IPv4: Vite's default `localhost` resolves to `::1`
    // first on Windows, which leaves the documented 127.0.0.1:3000 unreachable.
    host: "127.0.0.1",
    port: 3000,
    proxy: {
      "/api": backendTarget,
      "/v1": backendTarget,
      "/v1beta": backendTarget,
    },
  },
  plugins: [react(), tailwindcss()],
});
