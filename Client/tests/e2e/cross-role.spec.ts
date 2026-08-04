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
  await expect(page.getByText('Loading portfolio...')).not.toBeVisible({ timeout: 20_000 });
  await expect(page.getByText('Monthly Return')).toBeVisible();
  await expect(page.getByText('Performance period')).toBeVisible();
  const summaryResponse = await page.request.get('/api/portfolio/summary');
  expect(summaryResponse.status()).toBe(200);
  const summary = (await summaryResponse.json()).data as {
    fund_positions: Array<{ fund_id: number; units: number; market_value: number }>;
    fund_breakdown: Array<{ fund_id: number; units: number; amount: number }>;
  };
  expect(summary.fund_positions.length).toBeGreaterThan(2);
  expect(summary.fund_positions.every((position) => position.units > 0 && position.market_value > 0)).toBe(true);
  const investmentCard = page.getByRole('heading', { name: 'Fund Investments' }).locator('xpath=../..');
  await expect(investmentCard.locator('tbody tr')).toHaveCount(summary.fund_positions.length);
  expect(summary.fund_breakdown.length).toBe(new Set(summary.fund_positions.map((position) => position.fund_id)).size);

  const recentFlowsResponse = await page.request.get('/api/admin/fund-flows?page=1&page_size=5');
  expect(recentFlowsResponse.status()).toBe(200);
  const recentFlows = (await recentFlowsResponse.json()).data.flows as Array<{ id: number }>;
  const activityCard = page.getByRole('heading', { name: 'Recent Fund Activity' }).locator('xpath=../..');
  await expect(activityCard.locator('tbody tr')).toHaveCount(recentFlows.length);
  expect(await page.evaluate(() => localStorage.getItem('fundinv_token'))).toBeNull();
  const session = (await context.cookies()).find((cookie) => cookie.name === 'fundinv_session');
  expect(session?.httpOnly).toBe(true);
  const sessionUser = await page.evaluate(() => JSON.parse(localStorage.getItem('fundinv_user') || '{}'));
  expect(sessionUser.claims || []).not.toContain('executeTrades');

  await page.goto('/dashboard/investor/funds');
  await expect(page.getByText('Loading funds...')).not.toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole('button', { name: 'Buy Now' })).toHaveCount(0);
  const fundsResponse = await page.request.get('/api/funds/');
  expect(fundsResponse.status()).toBe(200);
  const fundProducts = (await fundsResponse.json()).data.funds as Array<{ fund_type: string }>;
  expect(fundProducts.every((fund) => fund.fund_type !== 'stock')).toBe(true);
  const directTrade = await page.request.post('/api/trading/buy', {
    data: { investment_account_id: 1, symbol: 'AAPL', amount: 1 },
  });
  expect(directTrade.status()).toBe(403);

  await page.goto('/dashboard/investor');
  await expect(page.getByRole('button', { name: 'Redeem' })).toHaveCount(0);

  const period = 'start_date=2000-01-01T00%3A00%3A00Z&end_date=2100-01-01T00%3A00%3A00Z';
  const pnlResponse = await page.request.get(`/api/portfolio/pnl?${period}`);
  expect(pnlResponse.status()).toBe(200);
  const pnlBody = await pnlResponse.json();
  const pnl = pnlBody.data.pnl as {
    total_pnl: number; realized_pnl: number; unrealized_pnl: number;
    portfolio_return_pct: number; fund_returns_pct: Record<string, number>;
  };
  for (const value of [pnl.total_pnl, pnl.realized_pnl, pnl.unrealized_pnl, pnl.portfolio_return_pct]) {
    expect(Number.isFinite(value)).toBe(true);
  }
  expect(pnl.unrealized_pnl).toBeCloseTo(pnl.total_pnl - pnl.realized_pnl, 6);
  for (const value of Object.values(pnl.fund_returns_pct)) expect(Number.isFinite(value)).toBe(true);

  const holdingsResponse = await page.request.get('/api/portfolio/holdings');
  expect(holdingsResponse.status()).toBe(200);
  const holdingsBody = await holdingsResponse.json();
  const holdings = holdingsBody.data.holdings as Array<{ daily_pnl: number }>;
  const holdingsPnl = holdings.reduce((sum, holding) => sum + holding.daily_pnl, 0);
  expect(pnl.total_pnl).toBeCloseTo(holdingsPnl, 6);

  await page.goto('/dashboard/investor/valuations');
  await expect(page.getByRole('heading', { name: 'My Fund P&L Allocations' })).toBeVisible();
  const valuationHistory = await page.request.get('/api/portfolio/valuation-history');
  expect(valuationHistory.status()).toBe(200);
  const managerValuations = await page.request.get('/api/manager/valuations');
  expect(managerValuations.status()).toBe(403);

  const forbidden = await page.request.get('/api/admin/stats');
  expect(forbidden.status()).toBe(403);
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
  const forbidden = await page.request.get('/api/portfolio/summary');
  expect(forbidden.status()).toBe(403);
  const managerValuations = await page.request.get('/api/manager/valuations');
  expect(managerValuations.status()).toBe(403);
});

test('manager can open attribution and what-if analysis', async ({ page }) => {
  await login(page, 'manager@fundinv.com', 'admin123', '/dashboard/manager');
  await page.goto('/dashboard/manager/performance');
  await expect(page.getByRole('heading', { name: 'Performance attribution' })).toBeVisible();
  await expect(page.getByText('Return drivers and scenario weights')).toBeVisible();

  await page.goto('/dashboard/manager/valuations');
  await expect(page.getByRole('heading', { name: 'Daily Fund Valuation' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Preview calculation' })).toBeVisible();
  const fundSelect = page.locator('select').first();
  await expect(fundSelect.locator('option')).toHaveCount(14);
  await fundSelect.selectOption({ label: 'Vanguard S&P 500 ETF' });
  await page.getByLabel('Valuation date').fill('2026-08-03');
  await expect(page.getByLabel('Daily fund P&L (USD)')).toHaveValue('74.37', { timeout: 20_000 });
  await expect(page.getByText('$74.37 from a +1.4568% fund return.')).toBeVisible();
  const historyResponse = await page.request.get('/api/manager/valuations');
  expect(historyResponse.status()).toBe(200);

  const fundsResponse = await page.request.get('/api/manager/funds');
  expect(fundsResponse.status()).toBe(200);
  const managedFunds = (await fundsResponse.json()).data.funds as Array<{
    id: number; fund_type: string; is_active: boolean; review_status: string;
  }>;
  const valuationEligible = managedFunds.filter(
    (fund) => fund.fund_type !== 'stock' && fund.is_active && fund.review_status === 'approved',
  );
  expect(valuationEligible).toHaveLength(13);

  const automaticSuggestion = await page.request.get(
    '/api/manager/valuations/suggestion?fund_id=2&valuation_date=2026-08-03',
  );
  expect(automaticSuggestion.status()).toBe(200);
  const suggestion = (await automaticSuggestion.json()).data as {
    available: boolean; suggested_daily_pnl: number | null; source: string | null;
  };
  expect(suggestion.available).toBe(true);
  expect(suggestion.suggested_daily_pnl).not.toBeNull();
  expect(suggestion.source).toBe('alpaca_daily_bars');

  const response = await page.request.get('/api/manager/performance-analysis');
  expect(response.status()).toBe(200);
  const body = await response.json();
  const analysis = body.data as { portfolio_return_pct: number; drivers: Array<{ contribution_pct: number }> };
  const contributionTotal = analysis.drivers.reduce((sum, driver) => sum + driver.contribution_pct, 0);
  expect(analysis.portfolio_return_pct).toBeCloseTo(contributionTotal, 8);
  const forbidden = await page.request.get('/api/admin/stats');
  expect(forbidden.status()).toBe(403);
});

test('admin can read administration data but not impersonate an investor portfolio', async ({ page }) => {
  await login(page, 'admin@fundinv.com', 'admin123', '/dashboard/admin');
  const stats = await page.request.get('/api/admin/stats');
  expect(stats.status()).toBe(200);
  const forbidden = await page.request.get('/api/portfolio/summary');
  expect(forbidden.status()).toBe(403);
  await page.goto('/dashboard/admin/valuations');
  await expect(page.getByRole('heading', { name: 'Fund Valuation Audit' })).toBeVisible();
  const valuations = await page.request.get('/api/admin/valuations');
  expect(valuations.status()).toBe(200);
});
