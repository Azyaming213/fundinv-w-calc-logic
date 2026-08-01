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
      command: 'NODE_OPTIONS=--max-old-space-size=2048 npm run build -- --webpack && npm run start -- --hostname localhost --port 3000',
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
