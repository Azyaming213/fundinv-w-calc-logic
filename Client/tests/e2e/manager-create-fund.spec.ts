import { execFileSync } from 'node:child_process';
import path from 'node:path';

import { expect, test } from '@playwright/test';

const runLiveCreation = process.env.RUN_MANAGER_CREATE_FUND_E2E === '1';
const fundName = `Playwright Create Fund ${Date.now()}`;

test.skip(!runLiveCreation, 'Set RUN_MANAGER_CREATE_FUND_E2E=1 to run the rollback-cleaned creation test.');

function removeTestFund() {
  const serverDir = path.resolve(process.cwd(), '../Server');
  const python = path.join(
    serverDir,
    process.platform === 'win32' ? 'venv/Scripts/python.exe' : 'venv/bin/python',
  );
  const cleanup = [
    'import sys',
    'from database import SessionLocal',
    'from models import AuditLog, Fund, FundComponent',
    'db = SessionLocal()',
    'funds = db.query(Fund).filter(Fund.name == sys.argv[1]).all()',
    'ids = [fund.id for fund in funds]',
    'db.query(AuditLog).filter(AuditLog.entity_type == "fund", AuditLog.entity_id.in_(ids)).delete(synchronize_session=False) if ids else None',
    'db.query(FundComponent).filter(FundComponent.fund_id.in_(ids)).delete(synchronize_session=False) if ids else None',
    '[db.delete(fund) for fund in funds]',
    'db.commit()',
    'db.close()',
  ].join('; ');
  execFileSync(python, ['-c', cleanup, fundName], { cwd: serverDir });
}

test.afterEach(() => removeTestFund());

test('manager creates, Operations approves, and Investor sees a live fund', async ({ page, context }) => {
  await page.goto('/login');
  await page.getByLabel('Email address').fill('manager@fundinv.com');
  await page.getByLabel('Password').fill('admin123');
  await page.locator('main form').getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/dashboard\/manager/);

  await page.goto('/dashboard/manager/funds');
  await page.getByRole('button', { name: '+ Create Fund', exact: true }).click();
  await expect(page.getByRole('heading', { name: 'Create New Fund' })).toBeVisible();

  await page.getByLabel('Fund Name').fill(fundName);
  await page.getByPlaceholder('Search underlying securities or approved funds...').fill('AAPL');
  const appleResult = page.getByRole('button', { name: /^AAPL/ }).first();
  await expect(appleResult).toBeVisible({ timeout: 20_000 });
  await appleResult.click();
  await page.locator('input[type="number"]').fill('100');

  const createResponse = page.waitForResponse((response) =>
    response.request().method() === 'POST'
    && response.url().endsWith('/api/manager/funds'),
  );
  await page.getByRole('button', { name: 'Create Fund', exact: true }).last().click();
  const response = await createResponse;
  expect(response.status()).toBe(200);
  const body = await response.json();
  expect(body.success).toBe(true);
  expect(body.data.name).toBe(fundName);
  expect(body.data.review_status).toBe('pending_ops_review');
  const fundId = body.data.id as number;

  await expect(page.getByText(`Fund "${fundName}" created successfully`)).toBeVisible();
  await expect(page.getByText(fundName, { exact: true })).toBeVisible();

  await context.clearCookies();
  await page.goto('/login');
  await page.evaluate(() => localStorage.clear());
  await page.getByLabel('Email address').fill('operations@fundinv.com');
  await page.getByLabel('Password').fill('admin123');
  await page.locator('main form').getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/dashboard\/operations/);
  const approval = await page.request.post(`/api/admin/fund-reviews/${fundId}`, {
    data: { decision: 'approve', notes: 'Playwright automatic visibility verification' },
  });
  expect(approval.status()).toBe(200);
  const approvalBody = await approval.json();
  expect(approvalBody.data.review_status).toBe('approved');
  expect(approvalBody.data.eligible_investors).toBeGreaterThan(0);

  await context.clearCookies();
  await page.goto('/login');
  await page.evaluate(() => localStorage.clear());
  await page.getByLabel('Email address').fill('investor@fundinv.com');
  await page.getByLabel('Password').fill('investor123');
  await page.locator('main form').getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/dashboard\/investor/);
  await page.goto('/dashboard/investor/funds');
  await expect(page.getByText('Loading funds...')).not.toBeVisible({ timeout: 20_000 });
  await expect(page.getByText(fundName, { exact: true })).toBeVisible();
});
