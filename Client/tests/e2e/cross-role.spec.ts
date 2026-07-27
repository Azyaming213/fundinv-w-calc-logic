import { expect, Page, test } from '@playwright/test';

async function login(page: Page, email: string, password: string, expectedPath: string) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.locator('main form').getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(new RegExp(expectedPath));
}

test('protected investor route redirects anonymous users', async ({ page }) => {
  await page.goto('/dashboard/investor');
  await expect(page).toHaveURL(/\/login\?from=/);
});

test('investor uses an HTTP-only session and sees reporting/security', async ({ page, context }) => {
  await login(page, 'investor@fundinv.com', 'investor123', '/dashboard/investor');
  await expect(page.getByRole('heading', { name: 'Portfolio Overview' })).toBeVisible();
  await expect(page.getByText('Monthly Return')).toBeVisible();
  await expect(page.getByText('Performance period')).toBeVisible();
  expect(await page.evaluate(() => localStorage.getItem('fundinv_token'))).toBeNull();
  const session = (await context.cookies()).find((cookie) => cookie.name === 'fundinv_session');
  expect(session?.httpOnly).toBe(true);
  await page.goto('/dashboard/investor/fund-flows');
  await expect(page.getByRole('heading', { name: 'Fund Flows' })).toBeVisible();
  await page.goto('/dashboard/security');
  await expect(page.getByRole('heading', { name: 'Account security' })).toBeVisible();
});

test('operations can review flows but cannot enter investor portfolio', async ({ page }) => {
  await login(page, 'operations@fundinv.com', 'admin123', '/dashboard/operations');
  await page.goto('/dashboard/operations/fund-flows');
  await expect(page.getByRole('heading', { name: 'Fund Flows' })).toBeVisible();
  await expect(page.getByText('Loading fund flows...')).not.toBeVisible();
  await page.goto('/dashboard/investor');
  await expect(page).toHaveURL(/\/unauthorized/);
});

test('manager can open attribution and what-if analysis', async ({ page }) => {
  await login(page, 'manager@fundinv.com', 'admin123', '/dashboard/manager');
  await page.goto('/dashboard/manager/performance');
  await expect(page.getByRole('heading', { name: 'Performance attribution' })).toBeVisible();
  await expect(page.getByText('Return drivers and scenario weights')).toBeVisible();
});
