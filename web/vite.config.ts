import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    // shadcn generates components that import from "@/..."; this is the alias
    // they expect, and it must match the paths entry in tsconfig.json.
    alias: { "@": path.resolve(import.meta.dirname, "src") },
  },
  server: {
    // Dev-only: `npm run dev` proxies the API to the Python server on 8080.
    // In Docker there is no proxy — FastAPI serves the built bundle itself.
    proxy: { "/api": "http://localhost:8080" },
  },
});
