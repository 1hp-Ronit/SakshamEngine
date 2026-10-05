import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

const backend = process.env.VITE_BACKEND_URL ?? 'http://localhost:8000'
const proxied = ['/api', '/mock', '/webhooks', '/demo', '/health']

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    allowedHosts: true, // lets an ngrok/cloudflared tunnel point at the dev server
    proxy: Object.fromEntries(proxied.map((p) => [p, { target: backend, changeOrigin: true }])),
  },
})
