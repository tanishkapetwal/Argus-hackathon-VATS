import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Dev server on :5173. VITE_API_BASE (default http://localhost:8000) points at the backend.
export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
});
