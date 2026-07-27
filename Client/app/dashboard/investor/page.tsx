'use client';

import { useState, useEffect, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from 'recharts';
import Card from '../../components/Card';
import Button from '../../components/Button';
import Input from '../../components/Input';
import { api, API_BASE } from '../../lib/api';
import { getUser } from '../../lib/auth';
import type {
  Transaction,
  Position,
  SellResult,
  PortfolioSummary,
  FundInvestmentItem,
  Fund,
  PnlReport,
} from '../../lib/types';

const CHART_COLORS = [
    '#2563EB', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6',
    '#EC4899', '#06B6D4', '#84CC16', '#F97316', '#6366F1',
];

const STRATEGIES = [
    { value: 'aggressive', label: 'Aggressive', desc: 'High risk, high reward' },
    { value: 'growth', label: 'Growth', desc: 'Focus on capital appreciation' },
    { value: 'balanced', label: 'Balanced', desc: 'Mix of growth and stability' },
    { value: 'conservative', label: 'Conservative', desc: 'Prioritize capital preservation' },
    { value: 'income', label: 'Income', desc: 'Focus on steady returns' },
];

export default function InvestorDashboard() {
    const router = useRouter();
    const [summary, setSummary] = useState<PortfolioSummary | null>(null);
    const [transactions, setTransactions] = useState<Transaction[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [emailSending, setEmailSending] = useState(false);
    const [emailSuccess, setEmailSuccess] = useState<string | null>(null);
    const [emailError, setEmailError] = useState<string | null>(null);
    const [exportingPdf, setExportingPdf] = useState(false);
    const [monthlyPnl, setMonthlyPnl] = useState<PnlReport | null>(null);
    const [periodPnl, setPeriodPnl] = useState<PnlReport | null>(null);
    const [periodStart, setPeriodStart] = useState(() => `${new Date().getFullYear()}-01-01`);
    const [periodEnd, setPeriodEnd] = useState(() => new Date().toISOString().slice(0, 10));
    const [periodLoading, setPeriodLoading] = useState(false);
    const [periodError, setPeriodError] = useState<string | null>(null);

    const [positions, setPositions] = useState<Position[]>([]);
    const [fundInvestments, setFundInvestments] = useState<FundInvestmentItem[]>([]);
    const [positionsError, setPositionsError] = useState<string | null>(null);
    const [sellPosition, setSellPosition] = useState<Position | null>(null);
    const [sellAmount, setSellAmount] = useState('');
    const [selling, setSelling] = useState(false);
    const [sellError, setSellError] = useState<string | null>(null);
    const [sellResult, setSellResult] = useState<SellResult | null>(null);

    const [showAccountModal, setShowAccountModal] = useState(false);
    const [accountName, setAccountName] = useState('');
    const [accountStrategy, setAccountStrategy] = useState('balanced');
    const [accountCurrency, setAccountCurrency] = useState('USD');
    const [creatingAccount, setCreatingAccount] = useState(false);
    const [accountError, setAccountError] = useState<string | null>(null);
    const [accountSuccess, setAccountSuccess] = useState<string | null>(null);

    const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
    const [showStrategyModal, setShowStrategyModal] = useState(false);
    const [editStrategy, setEditStrategy] = useState('');
    const [savingStrategy, setSavingStrategy] = useState(false);
    const [strategyError, setStrategyError] = useState<string | null>(null);

    const [showTopUpModal, setShowTopUpModal] = useState(false);
    const [topUpAccountId, setTopUpAccountId] = useState<number | null>(null);
    const [topUpAmount, setTopUpAmount] = useState('');
    const [topUpLoading, setTopUpLoading] = useState(false);
    const [topUpError, setTopUpError] = useState<string | null>(null);
    const [topUpResult, setTopUpResult] = useState<string | null>(null);
    const [funds, setFunds] = useState<Fund[]>([]);
    const [topUpFundId, setTopUpFundId] = useState<number | null>(null);

    const [showWithdrawModal, setShowWithdrawModal] = useState(false);
    const [withdrawAccountId, setWithdrawAccountId] = useState<number | null>(null);
    const [withdrawAmount, setWithdrawAmount] = useState('');
    const [withdrawLoading, setWithdrawLoading] = useState(false);
    const [withdrawError, setWithdrawError] = useState<string | null>(null);
    const [withdrawResult, setWithdrawResult] = useState<string | null>(null);
    const [withdrawFundId, setWithdrawFundId] = useState<number | null>(null);

    const user = getUser();

    const fetchData = async () => {
        setLoading(true);
        setError(null);
        try {
            const monthStart = new Date();
            monthStart.setUTCDate(1); monthStart.setUTCHours(0, 0, 0, 0);
            const [summaryRes, txnRes, monthlyRes] = await Promise.all([
                api.get<PortfolioSummary>('/api/portfolio/summary'),
                api.get<{ transactions: Transaction[] }>('/api/portfolio/recent-transactions'),
                api.get<{ pnl: PnlReport }>(`/api/portfolio/pnl?start_date=${encodeURIComponent(monthStart.toISOString())}&end_date=${encodeURIComponent(new Date().toISOString())}`),
            ]);
            setSummary(summaryRes);
            setTransactions(txnRes.transactions || []);
            setMonthlyPnl(monthlyRes.pnl);
            const fundsRes = await api.get<{ funds: Fund[] }>('/api/funds');
            setFunds(fundsRes.funds || []);
        } catch (err) {
            const msg = (err as { message?: string }).message || 'Failed to load portfolio';
            setError(msg);
        } finally {
            setLoading(false);
        }
    };

    const fetchPeriodPnl = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!periodStart || !periodEnd || periodStart > periodEnd) {
            setPeriodError('Choose a valid start and end date.');
            return;
        }
        setPeriodLoading(true); setPeriodError(null);
        try {
            const data = await api.get<{ pnl: PnlReport }>(`/api/portfolio/pnl?start_date=${encodeURIComponent(`${periodStart}T00:00:00Z`)}&end_date=${encodeURIComponent(`${periodEnd}T23:59:59Z`)}`);
            setPeriodPnl(data.pnl);
        } catch (err) {
            setPeriodError((err as { message?: string }).message || 'Unable to calculate period performance');
        } finally { setPeriodLoading(false); }
    };

    const fetchPositions = async () => {
        try {
            const data = await api.get<{ positions: Position[]; fund_investments: FundInvestmentItem[] }>('/api/funds/positions');
            setPositions(data.positions || []);
            setFundInvestments(data.fund_investments || []);
            setPositionsError(null);
        } catch (err) {
            setPositionsError((err as { message?: string }).message || 'Failed to load positions');
        }
    };

    useEffect(() => {
        fetchData();
        fetchPositions();
    }, []);

    const fmt = (n: number) =>
        new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);

    const pnlColor = (n: number) => {
        if (n > 0) return 'text-fundinv-success';
        if (n < 0) return 'text-fundinv-danger';
        return 'text-fundinv-muted';
    };

    const totalInvested = summary?.total_current_value ?? 0;
    const totalFundBalance = summary?.total_fund_balance ?? 0;

    const chartData = (summary?.fund_breakdown ?? []).map((f) => ({
        name: f.fund,
        value: f.amount,
        units: f.units ?? 0,
        navPerUnit: f.nav_per_unit ?? 0,
    }));

    const handlePieSegmentClick = (fund: string) => {
        router.push(`/dashboard/investor/stock/${encodeURIComponent(fund)}`);
    };

    const accounts = useMemo(() => summary?.accounts ?? [], [summary?.accounts]);
    const selectedAccount = accounts.find((a) => a.id === selectedAccountId) ?? accounts[0] ?? null;

    useEffect(() => {
        if (accounts.length > 0 && !selectedAccountId) {
            setSelectedAccountId(accounts[0].id);
        }
    }, [accounts, selectedAccountId]);

    const handleSaveStrategy = async () => {
        if (!selectedAccount) return;
        setSavingStrategy(true);
        setStrategyError(null);
        try {
            await api.put(`/api/portfolio/accounts/${selectedAccount.id}`, {
                investment_strategy: editStrategy,
            });
            setShowStrategyModal(false);
            await fetchData();
        } catch (err) {
            const msg = (err as { message?: string }).message || 'Failed to update strategy';
            setStrategyError(msg);
        } finally {
            setSavingStrategy(false);
        }
    };

    const strategyLabel = (val: string) => STRATEGIES.find((s) => s.value === val)?.label ?? val;

    const handleTopUp = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!topUpAccountId || !topUpAmount || !topUpFundId) return;
        const amount = parseFloat(topUpAmount);
        if (isNaN(amount) || amount <= 0) {
            setTopUpError('Please enter a valid amount');
            return;
        }
        setTopUpLoading(true);
        setTopUpError(null);
        try {
            const params = new URLSearchParams({
                investment_account_id: String(topUpAccountId),
                fund_id: String(topUpFundId),
                amount: String(amount),
            });
            const data = await api.post<{ request_id: string; amount: number; status: string; message: string }>(`/api/funds/deposit?${params}`);
            setTopUpResult(`Deposit request ${data.request_id} submitted. Amount: $${amount.toFixed(2)}. Status: ${data.status.replace(/_/g, ' ')}.`);
        } catch (err) {
            setTopUpError((err as { message?: string }).message || 'Deposit request failed');
        } finally {
            setTopUpLoading(false);
        }
    };

    const handleWithdraw = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!withdrawAccountId || !withdrawAmount || !withdrawFundId) return;
        const amount = parseFloat(withdrawAmount);
        if (isNaN(amount) || amount <= 0) {
            setWithdrawError('Please enter a valid amount');
            return;
        }
        const acct = accounts.find(a => a.id === withdrawAccountId);
        const available = acct ? Number(acct.manager_fund_balance[String(withdrawFundId)] || 0) : 0;
        if (amount > available) {
            setWithdrawError(`Insufficient available balance. Available: $${available.toFixed(2)}`);
            return;
        }
        setWithdrawLoading(true);
        setWithdrawError(null);
        try {
            const params = new URLSearchParams({
                investment_account_id: String(withdrawAccountId),
                fund_id: String(withdrawFundId),
                amount: String(amount),
            });
            const data = await api.post<{ request_id: string; amount: number; status: string; message: string }>(`/api/funds/withdraw?${params}`);
            setWithdrawResult(`Withdrawal request ${data.request_id} submitted. Amount: $${amount.toFixed(2)}. Status: ${data.status.replace(/_/g, ' ')}.`);
        } catch (err) {
            setWithdrawError((err as { message?: string }).message || 'Withdrawal request failed');
        } finally {
            setWithdrawLoading(false);
        }
    };

    const handleSendEmail = async () => {
        setEmailSending(true);
        setEmailSuccess(null);
        setEmailError(null);
        try {
            const res = await api.post<{ message: string }>('/api/portfolio/send-summary-email');
            setEmailSuccess(res.message || 'Email sent successfully');
        } catch (err) {
            const msg = (err as { message?: string }).message || 'Failed to send email';
            setEmailError(msg);
        } finally {
            setEmailSending(false);
        }
    };

    const handleExportPdf = async () => {
        setExportingPdf(true);
        try {
            const resp = await fetch(`${API_BASE}/api/portfolio/export-pdf`, {
                credentials: 'include',
            });
            if (!resp.ok) throw new Error('Export failed');
            const blob = await resp.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `FundInv_Portfolio.pdf`;
            a.click();
            window.URL.revokeObjectURL(url);
        } catch {
            // silent
        } finally {
            setExportingPdf(false);
        }
    };

    const handleSell = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!sellPosition || !selectedAccount) return;
        const amount = parseFloat(sellAmount);
        if (isNaN(amount) || amount <= 0) {
            setSellError('Please enter a valid amount');
            return;
        }
        setSelling(true);
        setSellError(null);
        try {
            const params = new URLSearchParams({ amount: String(amount), investment_account_id: String(selectedAccount.id) });
            if (sellPosition.fund_id) {
                params.set('fund_id', String(sellPosition.fund_id));
            }
            const result = await api.post<{ request_id: string; amount: number; status: string; message: string }>(`/api/funds/withdraw?${params}`);
            setSellResult({
                order_id: 0,
                alpaca_order_id: result.request_id,
                symbol: sellPosition.symbol,
                amount,
                status: result.status,
                position_market_value: sellPosition.market_value,
                sold_value: amount,
                remaining_position: sellPosition.market_value - amount,
            });
            fetchData();
            fetchPositions();
        } catch (err) {
            setSellError((err as { message?: string }).message || 'Redemption request failed');
        } finally {
            setSelling(false);
        }
    };

    const openSellModal = (pos: Position) => {
        setSellPosition(pos);
        setSellAmount(String(Math.min(pos.market_value, pos.market_value)));
        setSellError(null);
        setSellResult(null);
    };

    const closeSellModal = () => {
        setSellPosition(null);
        setSellError(null);
        setSellResult(null);
    };

    const handleCreateAccount = async (e: React.FormEvent) => {
        e.preventDefault();
        setCreatingAccount(true);
        setAccountError(null);
        setAccountSuccess(null);
        try {
            await api.post('/api/portfolio/accounts', {
                account_name: accountName,
                currency: accountCurrency,
                investment_strategy: accountStrategy,
            });
            setAccountSuccess('Account created successfully');
            setAccountName('');
            setAccountStrategy('balanced');
            setAccountCurrency('USD');
            await fetchData();
            setTimeout(() => {
                setShowAccountModal(false);
                setAccountSuccess(null);
            }, 1200);
        } catch (err) {
            const msg = (err as { message?: string }).message || 'Failed to create account';
            setAccountError(msg);
        } finally {
            setCreatingAccount(false);
        }
    };

    const resetAccountModal = () => {
        setShowAccountModal(false);
        setAccountName('');
        setAccountStrategy('balanced');
        setAccountCurrency('USD');
        setAccountError(null);
        setAccountSuccess(null);
    };

    return (
        <div className="max-w-6xl mx-auto px-8 py-8">
            <div className="flex items-center justify-between mb-8">
                <div>
                    <h1 className="text-2xl font-semibold text-fundinv-primary">Portfolio Overview</h1>
                    <p className="text-sm text-fundinv-muted mt-1">Welcome back, {user?.full_name || 'Investor'}</p>
                </div>
                <div className="flex gap-2">
                    <Button variant="primary" onClick={() => setShowAccountModal(true)}>
                        <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" /></svg>
                            Add Account
                        </span>
                    </Button>
                    <Button variant="primary" onClick={() => { setTopUpAccountId(selectedAccountId); setTopUpFundId(null); setTopUpAmount(''); setTopUpError(null); setTopUpResult(null); setShowTopUpModal(true); }}>
                        <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
                            Deposit to Fund
                        </span>
                    </Button>
                    <Button variant="secondary" onClick={() => { setWithdrawAccountId(selectedAccountId); setWithdrawFundId(null); setWithdrawAmount(''); setWithdrawError(null); setWithdrawResult(null); setShowWithdrawModal(true); }}>
                        <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7h12m0 0l-4-4m4 4l-4 4m0 6H4m0 0l4 4m-4-4l4-4" /></svg>
                            Withdraw
                        </span>
                    </Button>
                    <Button variant="secondary" onClick={handleExportPdf} disabled={exportingPdf}>
                        <span className="flex items-center gap-2">
                            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                            {exportingPdf ? 'Exporting...' : 'PDF'}
                        </span>
                    </Button>
                    <Button
                        variant="secondary"
                        onClick={handleSendEmail}
                        disabled={emailSending || loading}
                    >
                        {emailSending ? (
                            <span className="flex items-center gap-2">
                                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>
                                Sending...
                            </span>
                        ) : (
                            <span className="flex items-center gap-2">
                                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" /></svg>
                                Email Summary
                            </span>
                        )}
                    </Button>
                </div>
            </div>

            {accounts.length > 0 && (
                <div className="mb-4 flex items-center gap-4 p-3 bg-white border border-fundinv-border rounded-lg">
                    <div className="flex items-center gap-2">
                        <svg className="w-4 h-4 text-fundinv-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 10h18M7 15h1m4 0h1m-7 4h12a3 3 0 003-3V8a3 3 0 00-3-3H6a3 3 0 00-3 3v8a3 3 0 003 3z" /></svg>
                        <label className="text-sm font-medium text-fundinv-primary">Account:</label>
                        <select
                            value={selectedAccountId ?? ''}
                            onChange={(e) => setSelectedAccountId(Number(e.target.value))}
                            className="px-2 py-1 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                        >
                            {accounts.map((a) => (
                                <option key={a.id} value={a.id}>
                                    {a.account_name} ({a.account_number})
                                </option>
                            ))}
                        </select>
                    </div>

                    {selectedAccount && (
                        <div className="flex items-center gap-2 ml-auto">
                            <span className="text-sm text-fundinv-muted">Strategy:</span>
                            <span className="px-2.5 py-1 text-xs font-semibold rounded-full bg-blue-50 text-fundinv-accent border border-fundinv-accent/20">
                                {strategyLabel(selectedAccount.investment_strategy)}
                            </span>
                            <button
                                onClick={() => {
                                    setEditStrategy(selectedAccount.investment_strategy);
                                    setStrategyError(null);
                                    setShowStrategyModal(true);
                                }}
                                className="p-1 rounded-md text-fundinv-muted hover:text-fundinv-primary hover:bg-fundinv-surface transition"
                                title="Edit strategy"
                            >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" /></svg>
                            </button>
                        </div>
                    )}
                </div>
            )}

            {emailSuccess && (
                <div className="mb-4 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-md text-sm text-fundinv-success flex items-center gap-2">
                    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    {emailSuccess}
                </div>
            )}

            {emailError && (
                <div className="mb-4 px-4 py-2.5 bg-red-50 border border-red-200 rounded-md text-sm text-fundinv-danger flex items-center gap-2">
                    <svg className="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                    {emailError}
                </div>
            )}

            {loading ? (
                <div className="py-16 text-center text-sm text-fundinv-muted">Loading portfolio...</div>
            ) : error ? (
                <Card>
                    <div className="py-12 text-center">
                        <p className="text-sm text-fundinv-danger mb-3">{error}</p>
                        <Button variant="secondary" onClick={fetchData}>Retry</Button>
                    </div>
                </Card>
            ) : (
                <>
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                        <Card title="Account Value">
                            <p className="text-2xl font-semibold text-fundinv-primary">
                                {fmt(summary?.total_account_value ?? 0)}
                            </p>
                            <div className="flex gap-4 mt-2">
                                <div>
                                    <p className="text-xs text-fundinv-muted">Invested</p>
                                    <p className="text-sm font-medium text-fundinv-primary">{fmt(totalInvested)}</p>
                                </div>
                                <div className="border-l border-fundinv-border pl-4">
                                    <p className="text-xs text-fundinv-muted">In Fund Balance</p>
                                    <p className="text-sm font-medium text-fundinv-primary">{fmt(totalFundBalance)}</p>
                                </div>
                            </div>
                        </Card>

                        <Card title="Today's P&L">
                            <p className={`text-2xl font-semibold ${pnlColor(summary?.today_pnl ?? 0)}`}>
                                {fmt(summary?.today_pnl ?? 0)}
                            </p>
                            <p className="text-xs text-fundinv-muted mt-1">Allocated using opening fund units</p>
                        </Card>

                        <Card title="YTD Return">
                            <p className={`text-2xl font-semibold ${pnlColor(summary?.pnl?.portfolio_return_pct ?? 0)}`}>
                                {(summary?.pnl?.portfolio_return_pct ?? 0).toFixed(2)}%
                            </p>
                            <p className="text-xs text-fundinv-muted mt-1">Flow-adjusted, compounded daily</p>
                        </Card>
                        <Card title="Monthly Return">
                            <p className={`text-2xl font-semibold ${pnlColor(monthlyPnl?.portfolio_return_pct ?? 0)}`}>
                                {(monthlyPnl?.portfolio_return_pct ?? 0).toFixed(2)}%
                            </p>
                            <p className={`text-xs mt-1 ${pnlColor(monthlyPnl?.total_pnl ?? 0)}`}>{fmt(monthlyPnl?.total_pnl ?? 0)} P&amp;L</p>
                        </Card>
                    </div>

                    <Card title="Performance period" className="mb-6">
                        <form onSubmit={fetchPeriodPnl} className="flex flex-wrap items-end gap-3">
                            <Input label="Start date" type="date" value={periodStart} onChange={(e) => setPeriodStart(e.target.value)} />
                            <Input label="End date" type="date" value={periodEnd} onChange={(e) => setPeriodEnd(e.target.value)} />
                            <Button type="submit" disabled={periodLoading}>{periodLoading ? 'Calculating…' : 'Calculate'}</Button>
                        </form>
                        {periodError && <p className="mt-3 text-sm text-fundinv-danger">{periodError}</p>}
                        {periodPnl && (
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-5 pt-5 border-t border-fundinv-border">
                                <div><p className="text-xs text-fundinv-muted">Total dollar P&amp;L</p><p className={`font-semibold ${pnlColor(periodPnl.total_pnl)}`}>{fmt(periodPnl.total_pnl)}</p></div>
                                <div><p className="text-xs text-fundinv-muted">Compounded return</p><p className={`font-semibold ${pnlColor(periodPnl.portfolio_return_pct)}`}>{periodPnl.portfolio_return_pct.toFixed(2)}%</p></div>
                                <div><p className="text-xs text-fundinv-muted">Realized P&amp;L</p><p className={pnlColor(periodPnl.realized_pnl)}>{fmt(periodPnl.realized_pnl)}</p></div>
                                <div><p className="text-xs text-fundinv-muted">Unrealized P&amp;L</p><p className={pnlColor(periodPnl.unrealized_pnl)}>{fmt(periodPnl.unrealized_pnl)}</p></div>
                            </div>
                        )}
                    </Card>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
                        <Card title="Fund Allocation">
                            {chartData.length === 0 ? (
                                <div className="h-64 flex items-center justify-center text-sm text-fundinv-muted">
                                    No fund allocations yet
                                </div>
                            ) : (
                                <div className="h-72 min-h-[288px]">
                                    <ResponsiveContainer width="100%" height="100%">
                                        <PieChart>
                                            <Pie
                                                data={chartData}
                                                cx="50%"
                                                cy="50%"
                                                innerRadius={55}
                                                outerRadius={95}
                                                paddingAngle={3}
                                                dataKey="value"
                                                stroke="none"
                                            >
                                                {chartData.map((f, idx) => (
                                                    <Cell
                                                        key={idx}
                                                        fill={CHART_COLORS[idx % CHART_COLORS.length]}
                                                        onClick={() => handlePieSegmentClick(f.name)}
                                                        style={{ cursor: 'pointer' }}
                                                    />
                                                ))}
                                            </Pie>
                                            <Tooltip
                                                formatter={(value: number) => fmt(value)}
                                                contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #E2E8F0' }}
                                            />
                                        </PieChart>
                                    </ResponsiveContainer>
                                    <div className="text-center -mt-2">
                                        <p className="text-xs text-fundinv-muted">Click a segment to see stock details</p>
                                    </div>
                                </div>
                            )}

                            {chartData.length > 0 && (
                                <div className="flex flex-wrap gap-3 mt-2">
                                    {chartData.map((f, idx) => (
                                        <div key={f.name} className="flex items-center gap-1.5">
                                            <span
                                                className="w-2.5 h-2.5 rounded-full"
                                                style={{ backgroundColor: CHART_COLORS[idx % CHART_COLORS.length] }}
                                            />
                                            <span className="text-xs text-fundinv-primary font-medium">{f.name}</span>
                                            <span className="text-xs text-fundinv-muted">{fmt(f.value)}</span>
                                            {f.units > 0 && (
                                                <span className="text-xs text-fundinv-muted">
                                                    {f.units.toFixed(4)} units @ {fmt(f.navPerUnit)}
                                                </span>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            )}
                        </Card>

                        <Card title="Recent Transactions">
                            {transactions.length === 0 ? (
                                <div className="h-64 flex items-center justify-center text-sm text-fundinv-muted">
                                    No transactions yet
                                </div>
                            ) : (
                                <div className="overflow-x-auto -mx-6 max-h-80 overflow-y-auto">
                                    <table className="w-full text-sm">
                                        <thead className="sticky top-0 bg-white">
                                            <tr className="border-b border-fundinv-border">
                                                <th className="text-left py-2 px-6 font-medium text-fundinv-muted">Symbol</th>
                                                <th className="text-left py-2 px-2 font-medium text-fundinv-muted">Type</th>
                                                <th className="text-right py-2 px-2 font-medium text-fundinv-muted">Qty</th>
                                                <th className="text-right py-2 px-2 font-medium text-fundinv-muted">Price</th>
                                                <th className="text-right py-2 px-6 font-medium text-fundinv-muted">P&L</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {transactions.map((t) => (
                                                <tr key={t.id} className="border-b border-fundinv-border last:border-0">
                                                    <td className="py-2.5 px-6 font-medium text-fundinv-primary">{t.symbol}</td>
                                                    <td className="py-2.5 px-2">
                                                        <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded uppercase ${t.trade_type === 'buy' ? 'text-fundinv-success bg-emerald-50' : 'text-fundinv-danger bg-red-50'
                                                            }`}>
                                                            {t.trade_type}
                                                        </span>
                                                    </td>
                                                    <td className="py-2.5 px-2 text-right font-mono text-fundinv-muted">{t.volume}</td>
                                                    <td className="py-2.5 px-2 text-right font-mono text-fundinv-muted">${t.price.toFixed(2)}</td>
                                                    <td className={`py-2.5 px-6 text-right font-mono font-medium ${pnlColor(t.net_pnl)}`}>
                                                        {fmt(t.net_pnl)}
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </Card>
                    </div>

                    {positions.length > 0 ? (
                        <Card title="My Holdings">
                            <div className="overflow-x-auto -mx-6">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-fundinv-border">
                                            <th className="text-left py-2 px-6 font-medium text-fundinv-muted">Symbol</th>
                                            <th className="text-right py-2 px-2 font-medium text-fundinv-muted">Qty</th>
                                            <th className="text-right py-2 px-2 font-medium text-fundinv-muted">Mkt Value</th>
                                            <th className="text-right py-2 px-2 font-medium text-fundinv-muted">Avg Price</th>
                                            <th className="text-right py-2 px-2 font-medium text-fundinv-muted">Current</th>
                                            <th className="text-right py-2 px-2 font-medium text-fundinv-muted">P&L</th>
                                            <th className="text-right py-2 px-6 font-medium text-fundinv-muted">Sell</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {positions.map((p) => (
                                            <tr key={p.symbol} className="border-b border-fundinv-border last:border-0 hover:bg-fundinv-surface/50">
                                                <td className="py-2.5 px-6">
                                                    <button
                                                        onClick={() => handlePieSegmentClick(p.symbol)}
                                                        className="font-medium text-fundinv-accent hover:underline cursor-pointer"
                                                    >
                                                        {p.symbol}
                                                    </button>
                                                    {p.fund_name && <p className="text-xs text-fundinv-muted">{p.fund_name}</p>}
                                                </td>
                                                <td className="py-2.5 px-2 text-right font-mono text-fundinv-muted">{Number(p.qty).toFixed(4)}</td>
                                                <td className="py-2.5 px-2 text-right font-mono text-fundinv-primary font-medium">{fmt(p.market_value)}</td>
                                                <td className="py-2.5 px-2 text-right font-mono text-fundinv-muted">{fmt(p.avg_entry_price)}</td>
                                                <td className="py-2.5 px-2 text-right font-mono text-fundinv-muted">{fmt(p.current_price)}</td>
                                                <td className={`py-2.5 px-2 text-right font-mono font-medium ${pnlColor(p.unrealized_pl)}`}>
                                                    {fmt(p.unrealized_pl)} ({Number(p.unrealized_plpc).toFixed(1)}%)
                                                </td>
                                                <td className="py-2.5 px-6 text-right">
                                                        <Button variant="secondary" className="text-xs py-1 px-3 !text-amber-600 !border-amber-200 hover:!bg-amber-50" onClick={() => openSellModal(p)}>
                                                            Redeem
                                                        </Button>
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    ) : (
                        <Card title="My Holdings">
                            <div className="h-20 flex items-center justify-center text-sm text-fundinv-muted">
                                {positionsError ? (
                                    <span className="text-fundinv-danger">{positionsError}</span>
                                ) : (
                                    'No holdings yet. Buy stocks or funds to see them here.'
                                )}
                            </div>
                        </Card>
                    )}
                    {fundInvestments.length > 0 && (
                        <Card title="Fund Investments">
                            <div className="overflow-x-auto -mx-6">
                                <table className="w-full text-sm">
                                    <thead>
                                        <tr className="border-b border-fundinv-border">
                                            <th className="text-left py-2 px-6 font-medium text-fundinv-muted">Fund</th>
                                            <th className="text-left py-2 px-2 font-medium text-fundinv-muted">Type</th>
                                            <th className="text-right py-2 px-2 font-medium text-fundinv-muted">Amount</th>
                                            <th className="text-left py-2 px-2 font-medium text-fundinv-muted">Status</th>
                                            <th className="text-left py-2 px-6 font-medium text-fundinv-muted">Invested</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {fundInvestments.map((fi) => (
                                            <tr key={fi.id} className="border-b border-fundinv-border last:border-0 hover:bg-fundinv-surface/50">
                                                <td className="py-2.5 px-6 font-medium text-fundinv-primary">{fi.fund_name}</td>
                                                <td className="py-2.5 px-2">
                                                    <span className="px-1.5 py-0.5 text-[10px] font-medium rounded-full bg-fundinv-surface capitalize">
                                                        {fi.fund_type}
                                                    </span>
                                                </td>
                                                <td className="py-2.5 px-2 text-right font-mono text-fundinv-primary">{fmt(fi.amount)}</td>
                                                <td className="py-2.5 px-2">
                                                    <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded capitalize ${
                                                        fi.status === 'completed' || fi.status === 'allocated' ? 'text-fundinv-success bg-emerald-50' :
                                                        fi.status === 'pending' ? 'text-amber-600 bg-amber-50' :
                                                        'text-fundinv-muted bg-fundinv-surface'
                                                    }`}>
                                                        {fi.status}
                                                    </span>
                                                </td>
                                                <td className="py-2.5 px-6 text-xs text-fundinv-muted">
                                                    {fi.invested_at ? new Date(fi.invested_at).toLocaleDateString() : '—'}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        </Card>
                    )}
                </>
            )}

            {sellPosition && (
                <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
                    <div className="fixed inset-0 bg-black/40" onClick={closeSellModal} />
                    <div className="relative w-full max-w-md bg-white rounded-lg shadow-xl border border-fundinv-border">
                        <div className="px-6 py-4 border-b border-fundinv-border flex items-center justify-between">
                            <h2 className="text-lg font-semibold text-fundinv-primary">Request Redemption — {sellPosition.symbol}</h2>
                            <button onClick={closeSellModal} className="text-fundinv-muted hover:text-fundinv-primary transition" aria-label="Close">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="px-6 py-5">
                            {sellResult ? (
                                <div className="text-center py-4">
                                    <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-3">
                                        <svg className="w-6 h-6 text-fundinv-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                    </div>
                                    <p className="text-sm font-semibold text-fundinv-primary mb-1">Redemption Request Submitted</p>
                                    <p className="text-xs text-fundinv-muted mb-3">Requested withdrawal of ${sellResult.amount.toFixed(2)} from {sellResult.symbol}</p>
                                    <div className="bg-fundinv-surface rounded-md p-3 text-xs text-left mb-3">
                                        <div className="flex justify-between mb-1"><span className="text-fundinv-muted">Status</span><span className="font-medium text-amber-600 capitalize">{sellResult.status.replace(/_/g, ' ')}</span></div>
                                        <div className="flex justify-between"><span className="text-fundinv-muted">Request ID</span><span className="font-mono text-fundinv-primary">{sellResult.alpaca_order_id}</span></div>
                                    </div>
                                    <Button className="w-full" onClick={closeSellModal}>Done</Button>
                                </div>
                            ) : (
                                <form onSubmit={handleSell} className="flex flex-col gap-4">
                                    <div className="bg-fundinv-surface rounded-md p-3 flex items-center justify-between">
                                        <div>
                                            <p className="text-xs text-fundinv-muted">Market Value</p>
                                            <p className="text-sm font-semibold text-fundinv-primary">{fmt(sellPosition.market_value)}</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-xs text-fundinv-muted">P&L</p>
                                            <p className={`text-sm font-semibold ${pnlColor(sellPosition.unrealized_pl)}`}>
                                                {fmt(sellPosition.unrealized_pl)} ({Number(sellPosition.unrealized_plpc).toFixed(1)}%)
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex gap-2 flex-wrap">
                                        {[25, 50, 100, 250, 500].map((amt) => (
                                            <button key={amt} type="button" onClick={() => setSellAmount(String(Math.min(amt, sellPosition.market_value)))}
                                                className={`px-3 py-1.5 text-sm font-medium rounded-md border transition ${sellAmount === String(amt) ? 'border-fundinv-accent bg-fundinv-accent text-white' : 'border-fundinv-border text-fundinv-muted hover:border-fundinv-primary'
                                                    }`}
                                            >
                                                ${amt}
                                            </button>
                                        ))}
                                        <button type="button" onClick={() => setSellAmount(String(sellPosition.market_value))}
                                            className={`px-3 py-1.5 text-sm font-medium rounded-md border transition ${parseFloat(sellAmount) === sellPosition.market_value ? 'border-red-500 bg-red-50 text-red-700' : 'border-fundinv-border text-fundinv-muted hover:border-red-300'
                                                }`}
                                        >
                                            Max
                                        </button>
                                    </div>

                                    <Input label="Amount (USD)" type="number" placeholder="Enter amount" value={sellAmount}
                                        onChange={(e) => setSellAmount(e.target.value)} min="1" step="0.01" required disabled={selling}
                                    />
                                    <p className="text-xs text-fundinv-muted">Account: {selectedAccount?.account_name}</p>

                                    {sellError && <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md"><p className="text-sm text-red-700">{sellError}</p></div>}

                                    <div className="flex gap-2 mt-1">
                                        <Button type="button" variant="secondary" onClick={closeSellModal} disabled={selling} className="flex-1">Cancel</Button>
                                        <Button type="submit" disabled={selling || !sellAmount} className="flex-1">{selling ? 'Submitting...' : 'Submit Redemption Request'}</Button>
                                    </div>
                                </form>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {showAccountModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
                    <div className="fixed inset-0 bg-black/40" onClick={resetAccountModal} />
                    <div className="relative w-full max-w-md bg-white rounded-lg shadow-xl border border-fundinv-border">
                        <div className="px-6 py-4 border-b border-fundinv-border flex items-center justify-between">
                            <h2 className="text-lg font-semibold text-fundinv-primary">Add Investment Account</h2>
                            <button onClick={resetAccountModal} className="text-fundinv-muted hover:text-fundinv-primary transition" aria-label="Close">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="px-6 py-5">
                            {accountSuccess ? (
                                <div className="text-center py-4">
                                    <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-3">
                                        <svg className="w-6 h-6 text-fundinv-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                    </div>
                                    <p className="text-sm font-medium text-fundinv-primary">{accountSuccess}</p>
                                </div>
                            ) : (
                                <form onSubmit={handleCreateAccount} className="flex flex-col gap-4">
                                    <Input
                                        label="Account Name"
                                        type="text"
                                        placeholder="My Investment Account"
                                        value={accountName}
                                        onChange={(e) => setAccountName(e.target.value)}
                                        required
                                        disabled={creatingAccount}
                                    />

                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-sm font-medium text-fundinv-primary">Currency</label>
                                        <select
                                            value={accountCurrency}
                                            onChange={(e) => setAccountCurrency(e.target.value)}
                                            disabled={creatingAccount}
                                            className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                                        >
                                            <option value="USD">USD - US Dollar</option>
                                            <option value="EUR">EUR - Euro</option>
                                            <option value="GBP">GBP - British Pound</option>
                                        </select>
                                    </div>

                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-sm font-medium text-fundinv-primary">Investment Strategy</label>
                                        <div className="grid grid-cols-1 gap-2">
                                            {STRATEGIES.map((s) => (
                                                <label
                                                    key={s.value}
                                                    className={`flex items-center gap-3 px-3 py-2.5 rounded-md border cursor-pointer transition ${accountStrategy === s.value
                                                            ? 'border-fundinv-accent bg-blue-50'
                                                            : 'border-fundinv-border hover:border-fundinv-muted'
                                                        }`}
                                                >
                                                    <input
                                                        type="radio"
                                                        name="strategy"
                                                        value={s.value}
                                                        checked={accountStrategy === s.value}
                                                        onChange={(e) => setAccountStrategy(e.target.value)}
                                                        disabled={creatingAccount}
                                                        className="sr-only"
                                                    />
                                                    <span className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center ${accountStrategy === s.value ? 'border-fundinv-accent' : 'border-fundinv-border'
                                                        }`}>
                                                        {accountStrategy === s.value && (
                                                            <span className="w-2 h-2 rounded-full bg-fundinv-accent" />
                                                        )}
                                                    </span>
                                                    <div>
                                                        <p className="text-sm font-medium text-fundinv-primary">{s.label}</p>
                                                        <p className="text-xs text-fundinv-muted">{s.desc}</p>
                                                    </div>
                                                </label>
                                            ))}
                                        </div>
                                    </div>

                                    {accountError && (
                                        <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                                            <p className="text-sm text-red-700">{accountError}</p>
                                        </div>
                                    )}

                                    <div className="flex gap-2 mt-1">
                                        <Button type="button" variant="secondary" onClick={resetAccountModal} disabled={creatingAccount} className="flex-1">
                                            Cancel
                                        </Button>
                                        <Button type="submit" disabled={creatingAccount} className="flex-1">
                                            {creatingAccount ? 'Creating...' : 'Create Account'}
                                        </Button>
                                    </div>
                                </form>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {showStrategyModal && selectedAccount && (
                <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
                    <div className="fixed inset-0 bg-black/40" onClick={() => setShowStrategyModal(false)} />
                    <div className="relative w-full max-w-md bg-white rounded-lg shadow-xl border border-fundinv-border">
                        <div className="px-6 py-4 border-b border-fundinv-border flex items-center justify-between">
                            <h2 className="text-lg font-semibold text-fundinv-primary">Edit Strategy — {selectedAccount.account_name}</h2>
                            <button onClick={() => setShowStrategyModal(false)} className="text-fundinv-muted hover:text-fundinv-primary transition" aria-label="Close">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="px-6 py-5">
                            <p className="text-xs text-fundinv-muted mb-4">
                                Current: <span className="font-semibold text-fundinv-primary">{strategyLabel(selectedAccount.investment_strategy)}</span>
                            </p>
                            <div className="grid grid-cols-1 gap-2">
                                {STRATEGIES.map((s) => (
                                    <label
                                        key={s.value}
                                        className={`flex items-center gap-3 px-3 py-2.5 rounded-md border cursor-pointer transition ${editStrategy === s.value
                                                ? 'border-fundinv-accent bg-blue-50'
                                                : 'border-fundinv-border hover:border-fundinv-muted'
                                            }`}
                                    >
                                        <input
                                            type="radio"
                                            name="editStrategy"
                                            value={s.value}
                                            checked={editStrategy === s.value}
                                            onChange={(e) => setEditStrategy(e.target.value)}
                                            disabled={savingStrategy}
                                            className="sr-only"
                                        />
                                        <span className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center ${editStrategy === s.value ? 'border-fundinv-accent' : 'border-fundinv-border'
                                            }`}>
                                            {editStrategy === s.value && (
                                                <span className="w-2 h-2 rounded-full bg-fundinv-accent" />
                                            )}
                                        </span>
                                        <div>
                                            <p className="text-sm font-medium text-fundinv-primary">{s.label}</p>
                                            <p className="text-xs text-fundinv-muted">{s.desc}</p>
                                        </div>
                                    </label>
                                ))}
                            </div>

                            {strategyError && (
                                <div className="mt-3 px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                                    <p className="text-sm text-red-700">{strategyError}</p>
                                </div>
                            )}

                            <div className="flex gap-2 mt-4">
                                <Button variant="secondary" onClick={() => setShowStrategyModal(false)} disabled={savingStrategy} className="flex-1">
                                    Cancel
                                </Button>
                                <Button onClick={handleSaveStrategy} disabled={savingStrategy || editStrategy === selectedAccount.investment_strategy} className="flex-1">
                                    {savingStrategy ? 'Saving...' : 'Save Strategy'}
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>
            )}
            {showTopUpModal && (
                <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
                    <div className="fixed inset-0 bg-black/40" onClick={() => setShowTopUpModal(false)} />
                    <div className="relative w-full max-w-md bg-white rounded-lg shadow-xl border border-fundinv-border">
                        <div className="px-6 py-4 border-b border-fundinv-border flex items-center justify-between">
                            <h2 className="text-lg font-semibold text-fundinv-primary">Deposit to a Fund</h2>
                            <button onClick={() => setShowTopUpModal(false)} className="text-fundinv-muted hover:text-fundinv-primary transition" aria-label="Close">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="px-6 py-5">
                            {topUpResult ? (
                                <div className="text-center py-4">
                                    <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-3">
                                        <svg className="w-6 h-6 text-fundinv-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                    </div>
                                    <p className="text-sm font-medium text-fundinv-primary mb-2">Deposit Request Submitted</p>
                                    <p className="text-xs text-fundinv-muted">{topUpResult}</p>
                                    <Button className="w-full mt-4" onClick={() => setShowTopUpModal(false)}>Done</Button>
                                </div>
                            ) : (
                                <form onSubmit={handleTopUp} className="flex flex-col gap-4">
                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-sm font-medium text-fundinv-primary">Account</label>
                                        <select
                                            value={topUpAccountId ?? ''}
                                            onChange={(e) => setTopUpAccountId(Number(e.target.value))}
                                            disabled={topUpLoading}
                                            className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                                        >
                                            {accounts.length === 0 ? (
                                                <option value="">No accounts available</option>
                                            ) : (
                                                accounts.map((a) => (
                                                    <option key={a.id} value={a.id}>
                                                        {a.account_name} ({a.account_number})
                                                    </option>
                                                ))
                                            )}
                                        </select>
                                    </div>

                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-sm font-medium text-fundinv-primary">Fund</label>
                                        <select
                                            value={topUpFundId ?? ''}
                                            onChange={(e) => setTopUpFundId(Number(e.target.value))}
                                            disabled={topUpLoading}
                                            className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                                        >
                                            <option value="">Select an approved fund</option>
                                            {funds.map((fund) => <option key={fund.id} value={fund.id}>{fund.name}</option>)}
                                        </select>
                                    </div>

                                    <div className="flex gap-2 flex-wrap">
                                        {[100, 500, 1000, 5000, 10000].map((amt) => (
                                            <button
                                                key={amt}
                                                type="button"
                                                onClick={() => setTopUpAmount(String(amt))}
                                                className={`px-3 py-1.5 text-sm font-medium rounded-md border transition ${topUpAmount === String(amt) ? 'border-fundinv-accent bg-fundinv-accent text-white' : 'border-fundinv-border text-fundinv-muted hover:border-fundinv-primary'
                                                    }`}
                                            >
                                                ${amt}
                                            </button>
                                        ))}
                                    </div>

                                    <Input
                                        label="Amount (USD)"
                                        type="number"
                                        placeholder="Enter amount to deposit"
                                        value={topUpAmount}
                                        onChange={(e) => setTopUpAmount(e.target.value)}
                                        min="1"
                                        step="0.01"
                                        required
                                        disabled={topUpLoading}
                                    />

                                    <p className="text-xs text-fundinv-muted">
                                        Choose the fund that will receive the money. Operations approval is followed by payment; units appear only after Stripe confirms payment.
                                    </p>

                                    {topUpError && (
                                        <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                                            <p className="text-sm text-red-700">{topUpError}</p>
                                        </div>
                                    )}

                                    <div className="flex gap-2 mt-1">
                                        <Button type="button" variant="secondary" onClick={() => setShowTopUpModal(false)} disabled={topUpLoading} className="flex-1">
                                            Cancel
                                        </Button>
                                        <Button type="submit" disabled={topUpLoading || !topUpAccountId || !topUpFundId || !topUpAmount} className="flex-1">
                                            {topUpLoading ? 'Submitting...' : 'Submit Deposit Request'}
                                        </Button>
                                    </div>
                                </form>
                            )}
                        </div>
                    </div>
                </div>
            )}

            {showWithdrawModal && (() => {
                const wdAccount = accounts.find(a => a.id === withdrawAccountId);
                return (
                    <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
                        <div className="fixed inset-0 bg-black/40" onClick={() => setShowWithdrawModal(false)} />
                        <div className="relative w-full max-w-md bg-white rounded-lg shadow-xl border border-fundinv-border">
                            <div className="px-6 py-4 border-b border-fundinv-border flex items-center justify-between">
                                <h2 className="text-lg font-semibold text-fundinv-primary">Withdraw Funds</h2>
                                <button onClick={() => setShowWithdrawModal(false)} className="text-fundinv-muted hover:text-fundinv-primary transition" aria-label="Close">
                                    <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                    </svg>
                                </button>
                            </div>
                            <div className="px-6 py-5">
                                {withdrawResult ? (
                                    <div className="text-center py-4">
                                        <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-3">
                                            <svg className="w-6 h-6 text-fundinv-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                            </svg>
                                        </div>
                                        <p className="text-sm font-medium text-fundinv-primary mb-2">Withdrawal Request Submitted</p>
                                        <p className="text-xs text-fundinv-muted">{withdrawResult}</p>
                                        <Button className="w-full mt-4" onClick={() => setShowWithdrawModal(false)}>Done</Button>
                                    </div>
                                ) : (
                                    <form onSubmit={handleWithdraw} className="flex flex-col gap-4">
                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-sm font-medium text-fundinv-primary">Account</label>
                                            <select
                                                value={withdrawAccountId ?? ''}
                                                onChange={(e) => setWithdrawAccountId(Number(e.target.value))}
                                                disabled={withdrawLoading}
                                                className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                                            >
                                                {accounts.length === 0 ? (
                                                    <option value="">No accounts available</option>
                                                ) : (
                                                    accounts.map((a) => (
                                                        <option key={a.id} value={a.id}>
                                                            {a.account_name} — ${a.unallocated_balance.toFixed(2)} available
                                                        </option>
                                                    ))
                                                )}
                                        </select>
                                    </div>

                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-sm font-medium text-fundinv-primary">Fund</label>
                                        <select
                                            value={withdrawFundId ?? ''}
                                            onChange={(e) => setWithdrawFundId(Number(e.target.value))}
                                            disabled={withdrawLoading}
                                            className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                                        >
                                            <option value="">Select an approved fund</option>
                                            {funds.map((fund) => <option key={fund.id} value={fund.id}>{fund.name}</option>)}
                                        </select>
                                    </div>

                                        <div className="bg-fundinv-surface rounded-md p-3 flex items-center justify-between">
                                            <div>
                                                <p className="text-xs text-fundinv-muted">Available (Unallocated)</p>
                                        <p className="text-sm font-semibold text-fundinv-primary">
                                                    {(withdrawFundId && wdAccount ? Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) : 0).toLocaleString('en-US', { style: 'currency', currency: 'USD' })}
                                                </p>
                                            </div>
                                        </div>

                                        <div className="flex gap-2 flex-wrap">
                                            {[25, 50, 100, 250, 500].map((amt) => (
                                                <button
                                                    key={amt}
                                                    type="button"
                                                    onClick={() => setWithdrawAmount(String(Math.min(amt, withdrawFundId && wdAccount ? Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) : 0)))}
                                                    disabled={amt > (withdrawFundId && wdAccount ? Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) : 0)}
                                                    className={`px-3 py-1.5 text-sm font-medium rounded-md border transition ${amt > (withdrawFundId && wdAccount ? Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) : 0) ? 'opacity-40 cursor-not-allowed' : ''} ${withdrawAmount === String(Math.min(amt, withdrawFundId && wdAccount ? Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) : 0)) ? 'border-fundinv-accent bg-fundinv-accent text-white' : 'border-fundinv-border text-fundinv-muted hover:border-fundinv-primary'
                                                        }`}
                                                >
                                                    ${amt}
                                                </button>
                                            ))}
                                            <button
                                                type="button"
                                                onClick={() => setWithdrawAmount(String(withdrawFundId && wdAccount ? Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) : 0))}
                                                disabled={!(withdrawFundId && wdAccount) || Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) <= 0}
                                                className={`px-3 py-1.5 text-sm font-medium rounded-md border transition ${!(withdrawFundId && wdAccount) || Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) <= 0 ? 'opacity-40 cursor-not-allowed' : ''
                                                    } ${withdrawFundId && wdAccount && parseFloat(withdrawAmount) === Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) ? 'border-red-500 bg-red-50 text-red-700' : 'border-fundinv-border text-fundinv-muted hover:border-red-300'
                                                    }`}
                                            >
                                                Max
                                            </button>
                                        </div>

                                        <Input
                                            label="Amount (USD)"
                                            type="number"
                                            placeholder="Enter amount to withdraw"
                                            value={withdrawAmount}
                                            onChange={(e) => setWithdrawAmount(e.target.value)}
                                            min="1"
                                            step="0.01"
                                            max={withdrawFundId && wdAccount ? Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) : 0}
                                            required
                                            disabled={withdrawLoading}
                                        />

                                        <p className="text-xs text-fundinv-muted">
                                            Your withdrawal request will be reviewed by the operations team.
                                        </p>

                                        {withdrawError && (
                                            <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                                                <p className="text-sm text-red-700">{withdrawError}</p>
                                            </div>
                                        )}

                                        <div className="flex gap-2 mt-1">
                                            <Button type="button" variant="secondary" onClick={() => setShowWithdrawModal(false)} disabled={withdrawLoading} className="flex-1">
                                                Cancel
                                            </Button>
                                            <Button type="submit" disabled={withdrawLoading || !withdrawAccountId || !withdrawFundId || !withdrawAmount || !(withdrawFundId && wdAccount && Number(wdAccount.manager_fund_balance[String(withdrawFundId)] || 0) > 0)} className="flex-1">
                                                {withdrawLoading ? 'Submitting...' : 'Submit Withdrawal Request'}
                                            </Button>
                                        </div>
                                    </form>
                                )}
                            </div>
                        </div>
                    </div>
                );
            })()}
        </div>
    );
}
