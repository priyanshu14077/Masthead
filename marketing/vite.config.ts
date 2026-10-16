import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import { defineConfig } from "vite"

// The Masthead server serves this site at "/" and the app at "/app/". While editing the site with
// `npm run dev`, the app, API and sign-in are proxied to a running Masthead (uv run blog-studio).
const MASTHEAD = "http://127.0.0.1:8787" // STUDIO_PORT in Masthead's .env

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    fs: { allow: [".."] }, // prices come from ../plans.json, the file the app enforces
    proxy: { "/app": MASTHEAD, "/api": MASTHEAD, "/auth": MASTHEAD },
  },
})
