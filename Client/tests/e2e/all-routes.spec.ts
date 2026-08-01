import { expect, Page, test } from '@playwright/test';

const users = {
  investor: ['investor@fundinv.com', 'investor123'],
  manager: ['manager@fundinv.com', 'admin123'],
  operations: ['operations@fundinv.com', 'admin123'],
  admin: ['admin@fundinv.com', 'admin123'],
} as const;

const routes = {
  investor: [
    '/dashboard/investor',
    '/dashboard/investor/funds',
    '/dashboard/investor/fund-flows',
    '/dashboard/investor/valuations',
    '/dashboard/investor/articles',
    '/dashboard/investor/feedback',
    '/dashboard/security',
  ],
  manager: [
    '/dashboard/manager',
    '/dashboard/manager/funds',
    '/dashboard/manager/performance',
    '/dashboard/manager/valuations',
    '/dashboard/manager/transactions',
    '/dashboard/manager/articles',
    '/dashboard/security',
  ],
  operations: [
    '/dashboard/operations',
    '/dashboard/operations/fund-flows',
    '/dashboard/operations/fund-reviews',
    '/dashboard/operations/audit-logs',
    '/dashboard/operations/feedback',
    '/dashboard/operations/invite-requests',
    '/dashboard/security',
  ],
  admin: [
    '/dashboard/admin',
    '/dashboard/admin/audit-logs',
    '/dashboard/admin/fund-flows',
    '/dashboard/admin/valuations',
    '/dashboard/admin/transactions',
    '/dashboard/admin/users',
    '/dashboard/admin/investors',
    '/dashboard/admin/settings',
    '/dashboard/admin/articles',
    '/dashboard/security',
  ],
} as const;

async function login(page: Page, email: string, password: string) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.locator('main form').getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/dashboard\//);
}

for (const role of Object.keys(users) as Array<keyof typeof users>) {
  test(`${role} can render every owned route without browser or server errors`, async ({ page }) => {
    const failures: string[] = [];
    page.on('pageerror', (error) => failures.push(`pageerror: ${error.message}`));
    page.on('response', (response) => {
      if (response.status() >= 500) failures.push(`${response.status()} ${response.url()}`);
    });
    await login(page, users[role][0], users[role][1]);
    for (const route of routes[role]) {
      const response = await page.goto(route);
      expect(response?.status(), route).toBeLessThan(500);
      await expect(page.locator('body'), route).not.toContainText('Application error');
      await expect(page).toHaveURL(new RegExp(`${route.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?:[?#]|$)`));
    }
    expect(failures).toEqual([]);
  });
}

test('public authentication routes render', async ({ page }) => {
  for (const route of ['/', '/login', '/forgot-password', '/register', '/reset-password', '/unauthorized']) {
    const response = await page.goto(route);
    expect(response?.status(), route).toBeLessThan(500);
    await expect(page.locator('body')).not.toContainText('Application error');
  }
});
