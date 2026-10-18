import path from "node:path";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API port is written in exactly one place, `LENS_PORT`; `lens dev` exports
// it so this proxy follows the backend instead of duplicating the number.
const backendTarget =
  process.env.VITE_LENS_DEV_BACKEND ?? "http://127.0.0.1:18080";

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
    // The URL printed by `lens dev` is only correct on this port, so fail loudly
    // instead of moving to the next free one.
    strictPort: true,
    proxy: {
      "/api": backendTarget,
      "/v1": backendTarget,
      "/v1beta": backendTarget,
    },
  },
  plugins: [react(), tailwindcss()],
});
