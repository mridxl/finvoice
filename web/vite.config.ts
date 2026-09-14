import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    // Dev-only: `npm run dev` proxies the API to the Python server on 8080.
    // In Docker there is no proxy — FastAPI serves the built bundle itself.
    proxy: { "/api": "http://localhost:8080" },
  },
});
