import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the Vite server proxies /api to Django so the browser sees a single origin.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": process.env.VITE_API_PROXY || "http://localhost:8000" } },
});