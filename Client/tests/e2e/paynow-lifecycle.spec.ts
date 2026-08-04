import { expect, Page, test } from '@playwright/test';

async function login(page: Page, email: string, password: string, expectedPath: string) {
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password').fill(password);
  await page.locator('main form').getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(new RegExp(expectedPath));
}

async function switchUser(page: Page, email: string, password: string, expectedPath: string) {
  await page.context().clearCookies();
  await page.goto('/login');
  await page.evaluate(() => localStorage.clear());
  await login(page, email, password, expectedPath);
}

test('demo PayNow locks the amount and Operations completes it in one action', async ({ page }) => {
  test.skip(
    process.env.RUN_MUTATING_PAYNOW_E2E !== '1',
    'Set RUN_MUTATING_PAYNOW_E2E=1 to create and complete a $17.01 demo subscription.',
  );
  const browserFailures: string[] = [];
  page.on('pageerror', (error) => browserFailures.push(`pageerror: ${error.message}`));
  page.on('response', (response) => {
    if (response.status() >= 500) browserFailures.push(`${response.status()} ${response.url()}`);
  });

  const amount = 17.01;
  await login(page, 'investor@fundinv.com', 'investor123', '/dashboard/investor');
  await expect(page.getByText('Loading portfolio...')).not.toBeVisible({ timeout: 20_000 });
  await page.getByRole('button', { name: 'Deposit to Fund' }).click();

  const dialog = page.getByRole('heading', { name: 'Deposit to a Fund' }).locator('..').locator('..');
  const selects = dialog.locator('select');
  await expect(selects).toHaveCount(2);
  await selects.nth(1).selectOption({ index: 1 });
  const fundId = Number(await selects.nth(1).inputValue());
  expect(fundId).toBeGreaterThan(0);

  const amountInput = dialog.getByLabel('Amount (USD)');
  await expect(amountInput).toHaveAttribute('min', '1');
  await expect(amountInput).toHaveAttribute('max', '1000000');
  await expect(amountInput).toHaveAttribute('step', '0.01');
  await amountInput.fill('0');
  await expect(dialog.getByText('Enter an amount greater than $0.00 and no more than $1,000,000.00.')).toBeVisible();
  await expect(dialog.getByRole('button', { name: 'Generate Demo PayNow QR' })).toBeDisabled();
  await amountInput.fill(amount.toFixed(2));

  const depositResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST' && response.url().includes('/api/funds/deposit?'),
  );
  await dialog.getByRole('button', { name: 'Generate Demo PayNow QR' }).click();
  const depositResponse = await depositResponsePromise;
  expect(depositResponse.status()).toBe(200);
  const depositBody = await depositResponse.json();
  const flow = depositBody.data as { id: number; request_id: string; amount: number; fund_id: number };
  expect(flow.amount).toBe(amount);
  expect(flow.fund_id).toBe(fundId);

  await expect(page.getByText('Demo PayNow Payment', { exact: true })).toBeVisible();
  await expect(page.getByRole('img', { name: `Demo PayNow QR for ${flow.request_id}` })).toBeVisible();
  await expect(page.getByText(`USD ${amount.toFixed(2)}`, { exact: true })).toBeVisible();
  await expect(page.getByText('The QR locks the exact requested amount. The demo payment cannot submit a different amount.')).toBeVisible();

  const paymentResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST' && response.url().includes(`/api/funds/fund-flows/${flow.id}/simulate-paynow`),
  );
  await page.getByRole('button', { name: 'Simulate QR Scan & Payment' }).click();
  const paymentResponse = await paymentResponsePromise;
  expect(paymentResponse.status()).toBe(200);
  await expect(page.getByText('Demo Payment Recorded')).toBeVisible();
  await expect(page.getByText(`Requested and paid: USD ${amount.toFixed(2)}.`)).toBeVisible();

  const tamperAttempt = await page.request.post(`http://localhost:8000/api/funds/fund-flows/${flow.id}/simulate-paynow`, {
    data: { amount: amount + 1000 },
  });
  expect(tamperAttempt.status()).toBe(200);
  expect((await tamperAttempt.json()).data.paid_amount).toBe(amount);

  await switchUser(page, 'operations@fundinv.com', 'admin123', '/dashboard/operations');
  await page.goto('/dashboard/operations/fund-flows');
  await expect(page.getByText('Loading fund flows...')).not.toBeVisible({ timeout: 20_000 });
  await page.getByPlaceholder('Search by email, name, or request ID...').fill(flow.request_id);
  await page.getByRole('button', { name: 'Search' }).click();

  const row = page.getByRole('row').filter({ hasText: flow.request_id });
  await expect(row).toBeVisible();
  await expect(row.getByText('$17.01')).toHaveCount(2);
  await expect(row.getByText('pending ops team')).toBeVisible();
  await expect(row.getByRole('button', { name: 'Verify & Complete' })).toBeVisible();
  await expect(row.getByRole('button', { name: 'Approve' })).toHaveCount(0);
  await expect(row.getByRole('button', { name: 'Complete', exact: true })).toHaveCount(0);

  const completeResponsePromise = page.waitForResponse((response) =>
    response.request().method() === 'POST' && response.url().includes(`/api/admin/fund-flows/${flow.id}/verify-complete`),
  );
  await row.getByRole('button', { name: 'Verify & Complete' }).click();
  const completeResponse = await completeResponsePromise;
  expect(completeResponse.status()).toBe(200);
  await expect(row.getByText('completed', { exact: true })).toBeVisible({ timeout: 20_000 });
  await expect(row.getByRole('button', { name: 'Verify & Complete' })).toHaveCount(0);

  const repeatedCompletion = await page.request.post(
    `http://localhost:8000/api/admin/fund-flows/${flow.id}/verify-complete`,
    { data: {} },
  );
  expect(repeatedCompletion.status()).toBe(200);
  expect((await repeatedCompletion.json()).data.message).toContain('already verified and completed');

  expect(browserFailures).toEqual([]);
});
