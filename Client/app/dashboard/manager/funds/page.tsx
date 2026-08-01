'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';
import type { ManagerFund, StockResult, Holding, FundInvestor } from '../../../lib/types';

const STRATEGIES = [
  { value: 'aggressive', label: 'Aggressive', desc: 'High risk, high return. Leveraged and volatile assets.' },
  { value: 'growth', label: 'Growth', desc: 'Above-average growth potential with moderate-to-high risk.' },
  { value: 'balanced', label: 'Balanced', desc: 'Mix of growth and stability. Moderate risk.' },
  { value: 'conservative', label: 'Conservative', desc: 'Capital preservation. Low risk, steady returns.' },
  { value: 'income', label: 'Income', desc: 'Focus on dividends and yield. Low-to-moderate risk.' },
];

const RISK_LEVELS = ['low', 'low-medium', 'medium', 'medium-high', 'high'];

export default function FundsManagementPage() {
  const [funds, setFunds] = useState<ManagerFund[]>([]);
  const [loading, setLoading] = useState(true);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [fundInvestors, setFundInvestors] = useState<Record<number, FundInvestor[]>>({});
  const [investorsLoading, setInvestorsLoading] = useState<Record<number, boolean>>({});

  // Create form state
  const [showForm, setShowForm] = useState(false);
  const [fname, setFname] = useState('');
  const [fdesc, setFdesc] = useState('');
  const [fstrategy, setFstrategy] = useState('balanced');
  const [frisk, setFrisk] = useState('medium');
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Stock search
  const [stockQuery, setStockQuery] = useState('');
  const [stockResults, setStockResults] = useState<StockResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const searchRequestId = useRef(0);

  useEffect(() => {
    fetchFunds();
  }, []);

  async function fetchFunds() {
    setLoading(true);
    try {
      const data = await api.get<{ funds: ManagerFund[] }>('/api/manager/funds');
      setFunds(data.funds || []);
    } catch {
      setFunds([]);
    } finally {
      setLoading(false);
    }
  }

  const fetchFundInvestors = async (fundId: number) => {
    setInvestorsLoading((prev) => ({ ...prev, [fundId]: true }));
    try {
      const data = await api.get<{ investors: FundInvestor[] }>(`/api/manager/funds/${fundId}/investors`);
      setFundInvestors((prev) => ({ ...prev, [fundId]: data.investors || [] }));
    } catch {
      setFundInvestors((prev) => ({ ...prev, [fundId]: [] }));
    } finally {
      setInvestorsLoading((prev) => ({ ...prev, [fundId]: false }));
    }
  };

  const toggleExpand = (fundId: number) => {
    if (expandedId === fundId) {
      setExpandedId(null);
    } else {
      setExpandedId(fundId);
      if (!fundInvestors[fundId]) {
        fetchFundInvestors(fundId);
      }
    }
  };

  const searchStocks = useCallback(async (q: string) => {
    if (q.length < 1) {
      setStockResults([]);
      setShowDropdown(false);
      return;
    }
    const requestId = ++searchRequestId.current;
    setSearching(true);
    try {
      const data = await api.get<{ stocks: StockResult[] }>(`/api/manager/search-stocks?q=${encodeURIComponent(q)}`);
      if (requestId !== searchRequestId.current) return;
      setStockResults(data.stocks || []);
      setShowDropdown(true);
    } catch {
      if (requestId !== searchRequestId.current) return;
      setStockResults([]);
    } finally {
      if (requestId === searchRequestId.current) setSearching(false);
    }
  }, []);

  useEffect(() => {
    const query = stockQuery.trim();
    if (!query) {
      searchRequestId.current += 1;
      setStockResults([]);
      setShowDropdown(false);
      setSearching(false);
      return;
    }
    const timer = window.setTimeout(() => searchStocks(query), 300);
    return () => window.clearTimeout(timer);
  }, [stockQuery, searchStocks]);

  const addHolding = (stock: StockResult) => {
    if (holdings.find((h) => h.symbol === stock.symbol)) return;
    setHoldings([...holdings, { symbol: stock.symbol, name: stock.name, allocation: 0, asset_type: stock.asset_type, fund_id: stock.fund_id }]);
    setStockQuery('');
    setStockResults([]);
    setShowDropdown(false);
  };

  const updateAllocation = (index: number, value: number) => {
    const updated = [...holdings];
    updated[index] = { ...updated[index], allocation: Math.max(0, Math.min(100, value)) };
    setHoldings(updated);
  };

  const removeHolding = (index: number) => {
    setHoldings(holdings.filter((_, i) => i !== index));
  };

  const totalAllocation = holdings.reduce((sum, h) => sum + h.allocation, 0);

  const handleCreate = async () => {
    if (!fname.trim()) {
      setCreateErr('Fund name is required');
      return;
    }
    if (holdings.length === 0) {
      setCreateErr('Add at least one underlying security or approved fund');
      return;
    }
    if (Math.abs(totalAllocation - 100) > 0.01) {
      setCreateErr(`Portfolio allocations must total 100% (currently ${totalAllocation}%)`);
      return;
    }

    setCreating(true);
    setCreateErr(null);
    try {
      const payload = {
        name: fname.trim(),
        description: fdesc.trim(),
        strategy: fstrategy,
        risk_level: frisk,
        holdings: holdings.map((h) => ({ symbol: h.symbol, name: h.name, asset_type: h.asset_type, fund_id: h.fund_id, allocation: h.allocation })),
      };

      const res = await api.post<{ id: number; name: string; strategy: string }>('/api/manager/funds', payload);

      setToast(`Fund "${res.name}" created successfully`);
      resetForm();
      fetchFunds();
    } catch (err) {
      setCreateErr((err as { message?: string }).message || 'Failed to create fund');
    } finally {
      setCreating(false);
    }
  };

  const toggleFundActive = async (fund: ManagerFund) => {
    try {
      await api.put(`/api/funds/${fund.id}`, { is_active: !fund.is_active });
      fetchFunds();
    } catch {
    }
  };

  const resetForm = () => {
    setFname('');
    setFdesc('');
    setFstrategy('balanced');
    setFrisk('medium');
    setHoldings([]);
    setStockQuery('');
    setStockResults([]);
    setShowForm(false);
  };

  const fmt = (n: number) =>
    new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);

  const strategyColor = (s: string) => {
    switch (s) {
      case 'aggressive': return 'bg-red-50 text-red-700';
      case 'growth': return 'bg-blue-50 text-blue-700';
      case 'balanced': return 'bg-slate-100 text-slate-700';
      case 'conservative': return 'bg-emerald-50 text-emerald-700';
      case 'income': return 'bg-amber-50 text-amber-700';
      default: return 'bg-fundinv-surface text-fundinv-muted';
    }
  };

  const riskColor = (r: string | null) => {
    switch (r) {
      case 'low': return 'bg-emerald-100 text-emerald-700';
      case 'low-medium': return 'bg-green-100 text-green-700';
      case 'medium': return 'bg-amber-100 text-amber-700';
      case 'medium-high': return 'bg-orange-100 text-orange-700';
      case 'high': return 'bg-red-100 text-red-700';
      default: return 'bg-fundinv-surface text-fundinv-muted';
    }
  };

  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 4000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-fundinv-primary">Fund Management</h1>
          <p className="text-sm text-fundinv-muted mt-1">Create and manage your investment funds</p>
        </div>
        <Button onClick={() => { resetForm(); setShowForm(true); }}>
          + Create Fund
        </Button>
      </div>

      {toast && (
        <div className="mb-4 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-md text-sm text-emerald-700 flex items-center gap-2">
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
          {toast}
        </div>
      )}

      {/* Create Fund Form */}
      {showForm && (
        <Card className="mb-8 border-l-4 border-l-fundinv-accent">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-lg font-semibold text-fundinv-primary">Create New Fund</h2>
            <Button variant="secondary" onClick={resetForm} className="px-3 py-1 text-xs">Cancel</Button>
          </div>

          {/* Section 1: Fund Details */}
          <div className="mb-8">
            <h3 className="text-sm font-semibold text-fundinv-muted uppercase tracking-wider mb-4">Fund Details</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Input
                label="Fund Name"
                placeholder="e.g. Tech Growth Fund"
                value={fname}
                onChange={(e) => setFname(e.target.value)}
                required
              />
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-fundinv-primary">Description</label>
                <textarea
                  value={fdesc}
                  onChange={(e) => setFdesc(e.target.value)}
                  placeholder="Describe the fund's objective and approach..."
                  className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent resize-none"
                  rows={3}
                  maxLength={1000}
                />
              </div>
            </div>
          </div>

          {/* Section 2: Strategy & Risk */}
          <div className="mb-8">
            <h3 className="text-sm font-semibold text-fundinv-muted uppercase tracking-wider mb-4">Strategy & Risk</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="space-y-3">
                <label className="text-sm font-medium text-fundinv-primary">Strategy</label>
                {STRATEGIES.map((s) => (
                  <label
                    key={s.value}
                    className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition ${
                      fstrategy === s.value
                        ? 'border-fundinv-accent bg-blue-50/50'
                        : 'border-fundinv-border hover:border-fundinv-muted'
                    }`}
                  >
                    <input
                      type="radio"
                      name="strategy"
                      value={s.value}
                      checked={fstrategy === s.value}
                      onChange={(e) => setFstrategy(e.target.value)}
                      className="mt-0.5"
                    />
                    <div>
                      <span className="text-sm font-medium text-fundinv-primary">{s.label}</span>
                      <p className="text-xs text-fundinv-muted mt-0.5">{s.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
              <div className="flex flex-col gap-1.5">
                <label className="text-sm font-medium text-fundinv-primary">Risk Level</label>
                <div className="space-y-2">
                  {RISK_LEVELS.map((r) => (
                    <label
                      key={r}
                      className={`flex items-center gap-3 p-2.5 rounded-lg border cursor-pointer transition ${
                        frisk === r
                          ? 'border-fundinv-accent bg-blue-50/50'
                          : 'border-fundinv-border hover:border-fundinv-muted'
                      }`}
                    >
                      <input
                        type="radio"
                        name="risk"
                        value={r}
                        checked={frisk === r}
                        onChange={(e) => setFrisk(e.target.value)}
                      />
                      <span className={`px-2 py-0.5 text-xs font-medium rounded ${riskColor(r)}`}>{r}</span>
                    </label>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Section 3: Portfolio Composition */}
          <div className="mb-6">
            <h3 className="text-sm font-semibold text-fundinv-muted uppercase tracking-wider mb-4">
              Portfolio Composition
              <span className="text-fundinv-muted font-normal normal-case ml-2">(required, total 100%)</span>
            </h3>

            {/* Stock Search */}
            <div className="relative mb-4">
              <div className="flex gap-2">
                <div className="flex-1 relative">
                  <Input
                    placeholder="Search underlying securities or approved funds..."
                    value={stockQuery}
                    onChange={(e) => setStockQuery(e.target.value)}
                  />
                  {showDropdown && stockResults.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-white border border-fundinv-border rounded-md shadow-lg max-h-48 overflow-y-auto">
                      {stockResults.map((s) => (
                        <button
                          key={s.symbol}
                          type="button"
                          onClick={() => addHolding(s)}
                          className="w-full text-left px-3 py-2 text-sm hover:bg-fundinv-surface transition flex items-center justify-between"
                        >
                          <div>
                            <span className="font-medium text-fundinv-primary">{s.symbol}</span>
                            <span className="text-fundinv-muted ml-2 text-xs">{s.name}</span>
                          </div>
                          <span className="text-xs text-fundinv-accent">+ Add</span>
                        </button>
                      ))}
                    </div>
                  )}
                  {showDropdown && stockResults.length === 0 && !searching && stockQuery.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-white border border-fundinv-border rounded-md shadow-lg px-3 py-3 text-sm text-fundinv-muted">
                      No stocks found for &quot;{stockQuery}&quot;
                    </div>
                  )}
                </div>
              </div>
              {showDropdown && (
                <div className="fixed inset-0 z-0" onClick={() => setShowDropdown(false)} />
              )}
            </div>

            {/* Holdings List */}
            {holdings.length > 0 && (
              <div className="space-y-2 mb-3">
                {holdings.map((h, i) => (
                  <div key={h.symbol} className="flex items-center gap-3 p-3 bg-fundinv-surface rounded-lg">
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium text-fundinv-primary">{h.symbol}</p>
                      <p className="text-xs text-fundinv-muted truncate">{h.name}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <input
                        type="number"
                        value={h.allocation || ''}
                        onChange={(e) => updateAllocation(i, parseFloat(e.target.value) || 0)}
                        min={0}
                        max={100}
                        className="w-16 px-2 py-1 text-sm text-right border border-fundinv-border rounded-md focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                      />
                      <span className="text-sm text-fundinv-muted w-4">%</span>
                      <button
                        type="button"
                        onClick={() => removeHolding(i)}
                        className="text-red-500 hover:text-red-700 text-lg leading-none px-1"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                ))}
                <div className="flex items-center justify-between px-3 py-1.5">
                  <span className="text-xs text-fundinv-muted">Total Allocation</span>
                  <span className={`text-sm font-semibold ${totalAllocation === 100 ? 'text-emerald-600' : 'text-red-500'}`}>
                    {totalAllocation}%
                  </span>
                </div>
              </div>
            )}
          </div>

          {createErr && (
            <div className="mb-4 px-4 py-2.5 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
              {createErr}
            </div>
          )}

          <Button onClick={handleCreate} disabled={creating} className="w-full">
            {creating ? 'Creating...' : 'Create Fund'}
          </Button>
        </Card>
      )}

      {/* Fund List */}
      <Card title={`Your Funds (${funds.length})`}>
        {loading ? (
          <div className="py-12 text-center text-sm text-fundinv-muted">Loading funds...</div>
        ) : funds.length === 0 && !showForm ? (
          <div className="py-12 text-center">
            <p className="text-sm text-fundinv-muted mb-4">No funds created yet</p>
            <Button onClick={() => setShowForm(true)}>Create Your First Fund</Button>
          </div>
        ) : (
          <div className="-mx-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-fundinv-border">
                  <th className="text-left py-3 px-6 font-medium text-fundinv-muted w-8"></th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Name</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Strategy</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Risk</th>
                  <th className="text-center py-3 px-2 font-medium text-fundinv-muted">Holdings</th>
                  <th className="text-center py-3 px-2 font-medium text-fundinv-muted">Status</th>
                  <th className="text-right py-3 px-6 font-medium text-fundinv-muted">Actions</th>
                </tr>
              </thead>
              <tbody>
                {funds.map((fund) => (
                  <React.Fragment key={fund.id}>
                    <tr
                      key={fund.id}
                      className="border-b border-fundinv-border hover:bg-fundinv-surface/50 cursor-pointer transition"
                      onClick={() => toggleExpand(fund.id)}
                    >
                      <td className="py-3 px-6">
                        <svg
                          className={`w-4 h-4 text-fundinv-muted transition-transform ${expandedId === fund.id ? 'rotate-90' : ''}`}
                          fill="none" stroke="currentColor" viewBox="0 0 24 24"
                        >
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                        </svg>
                      </td>
                      <td className="py-3 px-2">
                        <span className="font-medium text-fundinv-primary">{fund.name}</span>
                        {fund.description && (
                          <p className="text-xs text-fundinv-muted mt-0.5 truncate max-w-[250px]">{fund.description}</p>
                        )}
                      </td>
                      <td className="py-3 px-2">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${strategyColor(fund.strategy)}`}>
                          {fund.strategy}
                        </span>
                      </td>
                      <td className="py-3 px-2">
                        <span className={`px-2 py-0.5 text-xs font-medium rounded ${riskColor(fund.risk_level)}`}>
                          {fund.risk_level || '—'}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-center text-fundinv-muted">
                        {(fund.portfolio_composition || []).length}
                      </td>
                      <td className="py-3 px-2 text-center">
                        <button
                          onClick={(e) => { e.stopPropagation(); toggleFundActive(fund); }}
                          className={`px-2 py-0.5 text-xs font-medium rounded-full transition ${
                            fund.is_active
                              ? 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100'
                              : 'bg-red-50 text-red-700 hover:bg-red-100'
                          }`}
                        >
                          {fund.is_active ? 'Active' : 'Inactive'}
                        </button>
                      </td>
                      <td className="py-3 px-6 text-right" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => toggleFundActive(fund)}
                          className="text-xs text-fundinv-muted hover:text-fundinv-primary mr-3"
                        >
                          {fund.is_active ? 'Deactivate' : 'Activate'}
                        </button>
                      </td>
                    </tr>

                    {/* Expanded Row */}
                    {expandedId === fund.id && (
                      <tr key={`${fund.id}-expanded`}>
                        <td colSpan={7} className="bg-fundinv-surface/30 px-6 py-4">
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                            {/* Composition */}
                            <div>
                              <h4 className="text-xs font-semibold text-fundinv-muted uppercase tracking-wider mb-3">
                                Portfolio Composition
                              </h4>
                              {(!fund.portfolio_composition || fund.portfolio_composition.length === 0) ? (
                                <p className="text-sm text-fundinv-muted">No holdings configured yet.</p>
                              ) : (
                                <div className="space-y-2">
                                  {fund.portfolio_composition.map((h, i) => (
                                    <div key={i} className="flex items-center justify-between p-2 bg-white rounded border border-fundinv-border">
                                      <div>
                                        <span className="text-sm font-medium text-fundinv-primary">{h.symbol}</span>
                                      </div>
                                      <span className="text-sm text-fundinv-muted">{h.allocation}%</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>

                            {/* Investors */}
                            <div>
                              <h4 className="text-xs font-semibold text-fundinv-muted uppercase tracking-wider mb-3">
                                Subscribed Investors
                              </h4>
                              {investorsLoading[fund.id] ? (
                                <p className="text-sm text-fundinv-muted">Loading investors...</p>
                              ) : !fundInvestors[fund.id] || fundInvestors[fund.id].length === 0 ? (
                                <p className="text-sm text-fundinv-muted">No investors subscribed yet.</p>
                              ) : (
                                <div className="space-y-2">
                                  {fundInvestors[fund.id].map((inv) => (
                                    <div key={inv.investor_id} className="flex items-center justify-between p-2 bg-white rounded border border-fundinv-border">
                                      <div>
                                        <p className="text-sm font-medium text-fundinv-primary">{inv.full_name}</p>
                                        <p className="text-xs text-fundinv-muted">{inv.email}</p>
                                      </div>
                                      <div className="text-right">
                                        <p className="text-sm font-semibold text-fundinv-primary">{fmt(inv.amount)}</p>
                                        <p className="text-xs text-fundinv-muted">
                                          {inv.invested_at ? new Date(inv.invested_at).toLocaleDateString() : '—'}
                                        </p>
                                      </div>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
