import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // 프로젝트 루트의 .env에서 키를 읽는다 (process.env가 우선)
  const env = { ...loadEnv(mode, path.resolve(__dirname, '..'), ''), ...process.env }

  return {
    base: './',
    plugins: [
      react(),
      {
        name: 'html-transform',
        transformIndexHtml(html: string) {
          return html
            .replace('$GOOGLE_MAPS_API_KEY', env.GOOGLE_MAPS_API_KEY || '$GOOGLE_MAPS_API_KEY')
            .replace('$SERVER_URL', env.SERVER_URL || 'http://localhost:10002')
        },
      },
    ],
  }
})
