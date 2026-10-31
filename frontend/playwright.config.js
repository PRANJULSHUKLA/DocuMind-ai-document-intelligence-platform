import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: './e2e', workers: 1, retries: 0,
  use: { baseURL: 'http://127.0.0.1:5201', headless: true },
  webServer: { command: 'VITE_AUTH_MODE=development VITE_API_BASE_URL=/api npm run dev -- --host 127.0.0.1 --port 5201 --strictPort', url: 'http://127.0.0.1:5201', reuseExistingServer: false },
})
