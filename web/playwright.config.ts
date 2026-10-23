import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './test/browser',
  fullyParallel: false,
  workers: 1,
  timeout: 30000,
  use: { baseURL: process.env.SPECCHECK_BROWSER_URL || 'http://127.0.0.1:8007',
    headless: true, viewport: { width: 1440, height: 1000 }, trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    launchOptions: process.env.SPECCHECK_CHROMIUM_PATH ? { executablePath: process.env.SPECCHECK_CHROMIUM_PATH } : {} },
})
