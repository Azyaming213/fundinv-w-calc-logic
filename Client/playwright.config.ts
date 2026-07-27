import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  fullyParallel: false,
  reporter: 'line',
  use: {
    baseURL: 'http://localhost:3000',
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'npm run dev -- --hostname 127.0.0.1',
      url: 'http://localhost:3000',
      reuseExistingServer: true,
      timeout: 120_000,
    },
    {
      command: '../Server/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000',
      cwd: '../Server',
      url: 'http://localhost:8000/api/test',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
});
