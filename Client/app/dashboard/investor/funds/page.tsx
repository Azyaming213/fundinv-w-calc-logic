'use client';

import { useState, useEffect, useCallback, useRef } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';
import type { Fund, AccountInfo, InvestResult } from '../../../lib/types';

const STRATEGIES = [
    { value: 'aggressive', label: 'Aggressive', color: 'text-red-600 bg-red-50 border-red-200', desc: 'High risk, high reward' },
    { value: 'growth', label: 'Growth', color: 'text-blue-600 bg-blue-50 border-blue-200', desc: 'Capital appreciation' },
    { value: 'balanced', label: 'Balanced', color: 'text-slate-600 bg-slate-100 border-slate-200', desc: 'Diversified mix' },
    { value: 'conservative', label: 'Conservative', color: 'text-emerald-600 bg-emerald-50 border-emerald-200', desc: 'Capital preservation' },
    { value: 'income', label: 'Income', color: 'text-amber-600 bg-amber-50 border-amber-200', desc: 'Steady returns' },
];

const FUND_TYPES = [
    { value: '', label: 'All Types' },
    { value: 'etf', label: 'ETF' },
    { value: 'bond', label: 'Bond' },
    { value: 'managed', label: 'Managed' },
];

const QUICK_AMOUNTS = [25, 50, 100, 250, 500];

export default function FundsPage() {
    const [funds, setFunds] = useState<Fund[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [activeStrategy, setActiveStrategy] = useState('');
    const [fundType, setFundType] = useState('');
    const [search, setSearch] = useState('');
    const [debouncedSearch, setDebouncedSearch] = useState('');
    const [sortBy, setSortBy] = useState('name');
    const debounceRef = useRef<NodeJS.Timeout | null>(null);

    const [accounts, setAccounts] = useState<AccountInfo[]>([]);
    const [investFund, setInvestFund] = useState<Fund | null>(null);
    const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
    const [investAmount, setInvestAmount] = useState('');
    const [investing, setInvesting] = useState(false);
    const [investError, setInvestError] = useState<string | null>(null);
    const [investResult, setInvestResult] = useState<InvestResult | null>(null);

    const fetchFunds = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            const params = new URLSearchParams();
            if (activeStrategy) params.set('strategy', activeStrategy);
            if (fundType) params.set('fund_type', fundType);
            if (debouncedSearch) params.set('search', debouncedSearch);
            if (sortBy) params.set('sort_by', sortBy);

            const qs = params.toString();
            const data = await api.get<{ funds: Fund[] }>(`/api/funds${qs ? `?${qs}` : ''}`);
            setFunds(data.funds || []);
        } catch (err) {
            setError((err as { message?: string }).message || 'Failed to load funds');
        } finally {
            setLoading(false);
        }
    }, [activeStrategy, fundType, debouncedSearch, sortBy]);

    const fetchAccounts = useCallback(async () => {
        try {
            const data = await api.get<{ accounts: AccountInfo[] }>('/api/portfolio/summary');
            setAccounts(data.accounts || []);
        } catch {
            // silent
        }
    }, []);

    useEffect(() => {
        if (debounceRef.current) clearTimeout(debounceRef.current);
        debounceRef.current = setTimeout(() => {
            setDebouncedSearch(search);
        }, 300);
        return () => {
            if (debounceRef.current) clearTimeout(debounceRef.current);
        };
    }, [search]);

    useEffect(() => {
        fetchFunds();
    }, [fetchFunds]);

    useEffect(() => {
        fetchAccounts();
    }, [fetchAccounts]);

    const openInvestModal = (fund: Fund) => {
        setInvestFund(fund);
        setInvestAmount('');
        setInvestError(null);
        setInvestResult(null);
        if (accounts.length > 0 && !selectedAccountId) {
            setSelectedAccountId(accounts[0].id);
        }
    };

    const closeInvestModal = () => {
        setInvestFund(null);
        setInvestError(null);
        setInvestResult(null);
    };

    const handleInvest = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!investFund || !selectedAccountId) return;

        const amount = parseFloat(investAmount);
        if (isNaN(amount) || amount <= 0) {
            setInvestError('Please enter a valid amount');
            return;
        }

        setInvesting(true);
        setInvestError(null);
        try {
            const result = await api.post<InvestResult>('/api/funds/invest', {
                fund_id: investFund.id,
                amount,
                investment_account_id: selectedAccountId,
            });
            setInvestResult(result);
            fetchAccounts();
        } catch (err) {
            setInvestError((err as { message?: string }).message || 'Investment failed');
        } finally {
            setInvesting(false);
        }
    };

    const fmt = (n: number | null) =>
        n != null ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n) : '—';

    const pctColor = (n: number | null) => {
        if (n == null) return 'text-fundinv-muted';
        if (n > 0) return 'text-fundinv-success';
        if (n < 0) return 'text-fundinv-danger';
        return 'text-fundinv-muted';
    };

    const strategyBadge = (s: string | null) => {
        const found = STRATEGIES.find((x) => x.value === s);
        return found ? found.color : 'text-fundinv-muted bg-fundinv-surface';
    };

    const selectedAccount = accounts.find((a) => a.id === selectedAccountId);

    const updateFundRisk = async (fundId: number, risk: string) => {
        try {
            await api.put(`/api/funds/${fundId}/risk-tolerance`, { risk_tolerance: risk });
            setFunds((current) => current.map((fund) => fund.id === fundId ? { ...fund, investor_risk_tolerance: risk as Fund['investor_risk_tolerance'] } : fund));
        } catch (err) {
            setError((err as { message?: string }).message || 'Unable to update risk tolerance');
        }
    };

    return (
        <div className="max-w-6xl mx-auto px-8 py-8">
            <div className="mb-8">
                <h1 className="text-2xl font-semibold text-fundinv-primary">Funds</h1>
                <p className="text-sm text-fundinv-muted mt-1">Invest in funds curated by your fund manager</p>
            </div>

            <Card className="mb-6">
                <div className="flex flex-wrap gap-2 mb-4">
                    <button
                        onClick={() => setActiveStrategy('')}
                        className={`px-3 py-1.5 text-sm font-medium rounded-md border transition ${activeStrategy === ''
                                ? 'border-fundinv-accent bg-fundinv-accent text-white'
                                : 'border-fundinv-border text-fundinv-muted hover:border-fundinv-primary hover:text-fundinv-primary'
                            }`}
                    >
                        All Strategies
                    </button>
                    {STRATEGIES.map((s) => (
                        <button
                            key={s.value}
                            onClick={() => setActiveStrategy(s.value)}
                            className={`px-3 py-1.5 text-sm font-medium rounded-md border transition ${activeStrategy === s.value
                                    ? 'border-fundinv-accent bg-fundinv-accent text-white'
                                    : 'border-fundinv-border text-fundinv-muted hover:border-fundinv-primary hover:text-fundinv-primary'
                                }`}
                        >
                            {s.label}
                        </button>
                    ))}
                </div>

                <div className="flex flex-wrap items-end gap-3">
                    <div className="flex-1 min-w-[150px]">
                        <Input
                            placeholder="Search by name or ticker..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                        />
                    </div>
                    <select
                        value={fundType}
                        onChange={(e) => setFundType(e.target.value)}
                        className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                    >
                        {FUND_TYPES.map((t) => (
                            <option key={t.value} value={t.value}>{t.label}</option>
                        ))}
                    </select>
                    <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value)}
                        className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                    >
                        <option value="name">Sort by Name</option>
                        <option value="ytd_return">Sort by YTD Return</option>
                        <option value="expense_ratio">Sort by Expense Ratio</option>
                    </select>
                </div>
            </Card>

            {loading ? (
                <div className="py-16 text-center text-sm text-fundinv-muted">Loading funds...</div>
            ) : error ? (
                <Card>
                    <div className="py-12 text-center">
                        <p className="text-sm text-fundinv-danger mb-3">{error}</p>
                        <Button variant="secondary" onClick={fetchFunds}>Retry</Button>
                    </div>
                </Card>
            ) : funds.length === 0 ? (
                <Card>
                    <div className="py-12 text-center text-sm text-fundinv-muted">
                        <p className="mb-2">No funds available. Please contact your manager.</p>
                    </div>
                </Card>
            ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">
                    {funds.map((fund) => (
                        <Card key={fund.id}>
                            <div className="flex items-start justify-between mb-2">
                                <div>
                                    <p className="text-sm font-semibold text-fundinv-primary">{fund.ticker || '—'}</p>
                                    <p className="text-xs text-fundinv-muted mt-0.5">{fund.name}</p>
                                </div>
                                <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-full border ${strategyBadge(fund.strategy)}`}>
                                    {fund.strategy || 'N/A'}
                                </span>
                            </div>

                            <div className="flex items-baseline gap-2 mb-2">
                                <p className="text-lg font-semibold text-fundinv-primary">{fmt(fund.current_price)}</p>
                                {fund.change_pct != null && (
                                    <span className={`text-xs font-medium ${pctColor(fund.change_pct)}`}>
                                        {fund.change_pct > 0 ? '+' : ''}{fund.change_pct.toFixed(2)}%
                                    </span>
                                )}
                            </div>

                            <div className="grid grid-cols-2 gap-2 text-xs mb-3">
                                <div>
                                    <p className="text-fundinv-muted">Type</p>
                                    <p className="font-medium text-fundinv-primary capitalize">{fund.fund_type}</p>
                                </div>
                                <div>
                                    <p className="text-fundinv-muted">Risk</p>
                                    <p className="font-medium text-fundinv-primary capitalize">{fund.risk_level || 'N/A'}</p>
                                </div>
                                {fund.manager_name && (
                                    <div className="col-span-2">
                                        <p className="text-fundinv-muted">Manager</p>
                                        <p className="font-medium text-fundinv-primary">{fund.manager_name}</p>
                                    </div>
                                )}
                                {fund.ytd_return != null && (
                                    <div>
                                        <p className="text-fundinv-muted">YTD Return</p>
                                        <p className={`font-medium ${pctColor(fund.ytd_return)}`}>
                                            {fund.ytd_return > 0 ? '+' : ''}{fund.ytd_return.toFixed(2)}%
                                        </p>
                                    </div>
                                )}
                                {fund.expense_ratio != null && (
                                    <div>
                                        <p className="text-fundinv-muted">Expense Ratio</p>
                                        <p className="font-medium text-fundinv-primary">{fund.expense_ratio.toFixed(2)}%</p>
                                    </div>
                                )}
                            </div>

                            {fund.description && (
                                <p className="text-xs text-fundinv-muted line-clamp-2 mb-3">{fund.description}</p>
                            )}

                            <label className="block text-xs text-fundinv-muted mb-3">
                                Your risk tolerance for this fund
                                <select
                                    value={fund.investor_risk_tolerance || 'balanced'}
                                    onChange={(e) => updateFundRisk(fund.id, e.target.value)}
                                    className="mt-1 w-full px-2 py-1.5 border border-fundinv-border rounded-md bg-white text-fundinv-primary"
                                >
                                    <option value="conservative">Conservative</option>
                                    <option value="balanced">Balanced</option>
                                    <option value="growth">Growth</option>
                                    <option value="aggressive">Aggressive</option>
                                </select>
                            </label>

                            {fund.ticker && fund.fund_type !== 'managed' && (
                                <Button variant="primary" className="w-full" onClick={() => openInvestModal(fund)}>
                                    Request to Buy {fund.ticker}
                                </Button>
                            )}
                            {fund.ticker && fund.fund_type === 'managed' && (
                                <Button variant="primary" className="w-full" onClick={() => openInvestModal(fund)}>
                                    Invest in {fund.ticker}
                                </Button>
                            )}
                            {!fund.ticker && fund.fund_type === 'managed' && (
                                <Button variant="primary" className="w-full" onClick={() => openInvestModal(fund)}>
                                    Invest in {fund.name}
                                </Button>
                            )}
                        </Card>
                    ))}
                </div>
            )}

            {investFund && (
                <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
                    <div className="fixed inset-0 bg-black/40" onClick={closeInvestModal} />
                    <div className="relative w-full max-w-md bg-white rounded-lg shadow-xl border border-fundinv-border">
                        <div className="px-6 py-4 border-b border-fundinv-border flex items-center justify-between">
                            <h2 className="text-lg font-semibold text-fundinv-primary">
                                {investFund.fund_type === 'managed'
                                    ? (investFund.ticker ? `Invest in ${investFund.ticker}` : `Invest in ${investFund.name}`)
                                    : (investFund.ticker ? `Request to Buy ${investFund.ticker}` : `Request to Buy ${investFund.name}`)
                                }
                            </h2>
                            <button onClick={closeInvestModal} className="text-fundinv-muted hover:text-fundinv-primary transition" aria-label="Close">
                                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                            </button>
                        </div>
                        <div className="px-6 py-5">
                            {investResult ? (
                                <div className="text-center py-4">
                                    <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-3">
                                        <svg className="w-6 h-6 text-fundinv-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                        </svg>
                                    </div>
                                    <p className="text-sm font-semibold text-fundinv-primary mb-1">
                                        {investFund.fund_type === 'managed' ? 'Fund Investment Placed' : 'Investment Request Submitted'}
                                    </p>
                                    <p className="text-xs text-fundinv-muted mb-3">
                                        {investFund.fund_type === 'managed'
                                            ? `$${investResult.amount.toFixed(2)} allocated to ${investResult.fund_name || investFund.name}`
                                            : `Requested $${investResult.amount.toFixed(2)} in ${investFund.ticker || investFund.name}. Pending manager review.`
                                        }
                                    </p>
                                    <div className="bg-fundinv-surface rounded-md p-3 text-xs text-left mb-3">
                                        <div className="flex justify-between mb-1">
                                            <span className="text-fundinv-muted">Status</span>
                                            <span className={`font-medium capitalize ${investResult.status === 'pending' ? 'text-amber-600' : 'text-fundinv-success'}`}>{investResult.status}</span>
                                        </div>
                                        {investResult.message && (
                                            <div className="flex justify-between">
                                                <span className="text-fundinv-muted">Note</span>
                                                <span className="font-medium text-fundinv-primary text-right ml-2">{investResult.message}</span>
                                            </div>
                                        )}
                                        {investResult.remaining_balance != null && (
                                            <div className="flex justify-between mb-1">
                                                <span className="text-fundinv-muted">Remaining</span>
                                                <span className="font-medium text-fundinv-primary">${investResult.remaining_balance.toFixed(2)}</span>
                                            </div>
                                        )}
                                    </div>
                                    <Button className="w-full" onClick={closeInvestModal}>Done</Button>
                                </div>
                            ) : (
                                <form onSubmit={handleInvest} className="flex flex-col gap-4">
                                    <div className="bg-fundinv-surface rounded-md p-3 flex items-center justify-between">
                                        <div>
                                            <p className="text-xs text-fundinv-muted">Current Price</p>
                                            <p className="text-sm font-semibold text-fundinv-primary">{fmt(investFund.current_price)}</p>
                                        </div>
                                        <div className="text-right">
                                            <p className="text-xs text-fundinv-muted">Change</p>
                                            <p className={`text-sm font-semibold ${pctColor(investFund.change_pct)}`}>
                                                {investFund.change_pct != null ? `${investFund.change_pct > 0 ? '+' : ''}${investFund.change_pct.toFixed(2)}%` : '—'}
                                            </p>
                                        </div>
                                    </div>

                                    <div className="flex flex-col gap-1.5">
                                        <label className="text-sm font-medium text-fundinv-primary">Fund Account</label>
                                        <select
                                            value={selectedAccountId ?? ''}
                                            onChange={(e) => setSelectedAccountId(Number(e.target.value))}
                                            disabled={investing}
                                            className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                                        >
                                            {accounts.length === 0 ? (
                                                <option value="">No accounts available</option>
                                            ) : (
                                                accounts.map((a) => (
                                                    <option key={a.id} value={a.id}>
                                                        {a.account_name} — ${a.fund_balance.toFixed(2)}
                                                    </option>
                                                ))
                                            )}
                                        </select>
                                    </div>

                                    <div className="flex gap-2 flex-wrap">
                                        {QUICK_AMOUNTS.map((amt) => (
                                            <button
                                                key={amt}
                                                type="button"
                                                onClick={() => setInvestAmount(String(amt))}
                                                className={`px-3 py-1.5 text-sm font-medium rounded-md border transition ${investAmount === String(amt)
                                                        ? 'border-fundinv-accent bg-fundinv-accent text-white'
                                                        : 'border-fundinv-border text-fundinv-muted hover:border-fundinv-primary hover:text-fundinv-primary'
                                                    }`}
                                            >
                                                ${amt}
                                            </button>
                                        ))}
                                    </div>

                                    <Input
                                        label="Amount (USD)"
                                        type="number"
                                        placeholder="Enter amount"
                                        value={investAmount}
                                        onChange={(e) => setInvestAmount(e.target.value)}
                                        min="1"
                                        step="0.01"
                                        required
                                        disabled={investing}
                                    />

                                    {investAmount && selectedAccount && (
                                        <p className="text-xs text-fundinv-muted">
                                            {selectedAccount.account_name}: ${selectedAccount.fund_balance.toFixed(2)} available
                                        </p>
                                    )}

                                    {investError && (
                                        <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                                            <p className="text-sm text-red-700">{investError}</p>
                                        </div>
                                    )}

                                    <div className="flex gap-2 mt-1">
                                        <Button type="button" variant="secondary" onClick={closeInvestModal} disabled={investing} className="flex-1">
                                            Cancel
                                        </Button>
                                        <Button type="submit" disabled={investing || !selectedAccountId || !investAmount} className="flex-1">
                                            {investing ? 'Placing Order...' : 'Buy Now'}
                                        </Button>
                                    </div>
                                </form>
                            )}
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
