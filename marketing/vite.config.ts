import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"

// Prices come from ../plans.json, the same file the app enforces, so the dev server may read one level up.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { fs: { allow: [".."] } },
})
