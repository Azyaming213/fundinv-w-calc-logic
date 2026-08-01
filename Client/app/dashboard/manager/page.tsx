'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import Card from '../../components/Card';
import Button from '../../components/Button';
import { api } from '../../lib/api';
import type { ManagerInvestor, ManagerFund } from '../../lib/types';

export default function ManagerDashboard() {
  const [investors, setInvestors] = useState<ManagerInvestor[]>([]);
  const [funds, setFunds] = useState<ManagerFund[]>([]);
  const [loading, setLoading] = useState(true);

  async function fetchData() {
    setLoading(true);
    try {
      const [invRes, fundRes] = await Promise.all([
        api.get<{ investors: ManagerInvestor[] }>('/api/manager/investors'),
        api.get<{ funds: ManagerFund[] }>('/api/manager/funds'),
      ]);
      setInvestors(invRes.investors || []);
      setFunds(fundRes.funds || []);
    } catch {
      setInvestors([]);
      setFunds([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    fetchData();
  }, []);

  const activeFunds = funds.filter((f) => f.is_active);
  const activeInvestors = investors.filter((i) => i.is_active);
  // Fund holdings are the investor-facing value. Underlying securities are the
  // composition of those funds, so adding them again would double-count AUM.
  const totalAUM = investors.reduce((sum, i) => sum + (i.total_in_funds || 0), 0);

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

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-8 py-8">
        <div className="py-16 text-center text-sm text-fundinv-muted">Loading...</div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-fundinv-primary">Manager Dashboard</h1>
        <p className="text-sm text-fundinv-muted mt-1">Manage your investors and funds</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        <Card>
          <div className="py-2 text-center">
            <p className="text-3xl font-bold text-fundinv-primary">{activeFunds.length}</p>
            <p className="text-sm text-fundinv-muted mt-1">Active Funds</p>
          </div>
        </Card>
        <Card>
          <div className="py-2 text-center">
            <p className="text-3xl font-bold text-fundinv-primary">{activeInvestors.length}</p>
            <p className="text-sm text-fundinv-muted mt-1">Active Investors</p>
          </div>
        </Card>
        <Card>
          <div className="py-2 text-center">
            <p className="text-3xl font-bold text-fundinv-primary">{fmt(totalAUM)}</p>
            <p className="text-sm text-fundinv-muted mt-1">Total AUM</p>
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="md:col-span-2">
          <Card title="Your Investors">
            {investors.length === 0 ? (
              <div className="py-6 text-center text-sm text-fundinv-muted">No investors assigned yet</div>
            ) : (
              <div className="overflow-x-auto -mx-6">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-fundinv-border">
                      <th className="text-left py-2.5 px-6 font-medium text-fundinv-muted">Investor</th>
                      <th className="text-left py-2.5 px-2 font-medium text-fundinv-muted">Status</th>
                      <th className="text-right py-2.5 px-2 font-medium text-fundinv-muted">Fund Value</th>
                      <th className="text-right py-2.5 px-6 font-medium text-fundinv-muted">Underlying Exposure</th>
                    </tr>
                  </thead>
                  <tbody>
                    {investors.slice(0, 10).map((inv) => (
                      <tr key={inv.id} className="border-b border-fundinv-border last:border-0">
                        <td className="py-2.5 px-6">
                          <div className="text-fundinv-primary font-medium">{inv.full_name}</div>
                          <div className="text-xs text-fundinv-muted">{inv.email}</div>
                        </td>
                        <td className="py-2.5 px-2">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                            inv.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-red-50 text-red-700'
                          }`}>
                            {inv.is_active ? 'Active' : 'Inactive'}
                          </span>
                        </td>
                        <td className="py-2.5 px-2 text-right text-fundinv-primary">{fmt(inv.total_in_funds || 0)}</td>
                        <td className="py-2.5 px-6 text-right text-fundinv-muted">{fmt(inv.total_in_stocks || 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>

        <div>
          <Card title="Actions">
            <div className="flex flex-col gap-3 py-2">
              <Link href="/dashboard/manager/funds">
                <Button className="w-full">Manage Funds</Button>
              </Link>
              <Link href="/dashboard/manager/transactions">
                <Button variant="secondary" className="w-full">View Transactions</Button>
              </Link>
            </div>
          </Card>

          <Card title="Your Funds" className="mt-4">
            {funds.length === 0 ? (
              <div className="py-4 text-center text-sm text-fundinv-muted">No funds created yet</div>
            ) : (
              <div className="divide-y divide-fundinv-border">
                {funds.slice(0, 5).map((f) => (
                  <div key={f.id} className="py-2.5 flex items-center justify-between">
                    <div>
                      <p className="text-sm font-medium text-fundinv-primary">{f.name}</p>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className={`px-1.5 py-0.5 text-[10px] font-medium rounded ${strategyColor(f.strategy)}`}>
                          {f.strategy}
                        </span>
                        <span className={`w-1.5 h-1.5 rounded-full ${f.is_active ? 'bg-emerald-500' : 'bg-red-400'}`} />
                      </div>
                    </div>
                    <span className="text-xs text-fundinv-muted">
                      {f.risk_level || '—'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
