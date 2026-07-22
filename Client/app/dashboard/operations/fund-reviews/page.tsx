'use client';

import { useEffect, useState } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import { api } from '../../../lib/api';

type ReviewFund = { id: number; name: string; description: string | null; strategy: string | null; risk_level: string | null; portfolio_composition: { symbol: string; allocation: number }[] };

export default function FundReviewsPage() {
  const [funds, setFunds] = useState<ReviewFund[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      const data = await api.get<{ funds: ReviewFund[] }>('/api/admin/fund-reviews');
      setFunds(data.funds || []);
    } catch (err) {
      setError((err as { message?: string }).message || 'Failed to load fund reviews');
    }
  };

  useEffect(() => { load(); }, []);

  const review = async (fundId: number, decision: 'approve' | 'reject') => {
    const notes = decision === 'reject' ? window.prompt('Reason for rejection') || 'Rejected by operations' : undefined;
    try {
      await api.post(`/api/admin/fund-reviews/${fundId}`, { decision, notes });
      await load();
    } catch (err) {
      setError((err as { message?: string }).message || 'Review failed');
    }
  };

  return <div className="max-w-6xl mx-auto px-8 py-8">
    <div className="mb-8"><h1 className="text-2xl font-semibold text-fundinv-primary">Fund Reviews</h1><p className="text-sm text-fundinv-muted mt-1">Approve manager funds before they become available to investors.</p></div>
    {error && <p className="mb-4 text-sm text-red-600">{error}</p>}
    <div className="space-y-4">{funds.map((fund) => <Card key={fund.id}>
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div><h2 className="font-semibold text-fundinv-primary">{fund.name}</h2><p className="text-sm text-fundinv-muted">{fund.description || 'No description'}</p><p className="text-xs text-fundinv-muted mt-2">{fund.strategy} · {fund.risk_level}</p><div className="flex flex-wrap gap-2 mt-3">{(fund.portfolio_composition || []).map((item) => <span key={item.symbol} className="px-2 py-1 text-xs rounded bg-fundinv-surface">{item.symbol} {item.allocation}%</span>)}</div></div>
        <div className="flex gap-2 shrink-0"><Button onClick={() => review(fund.id, 'approve')}>Approve</Button><Button variant="secondary" onClick={() => review(fund.id, 'reject')} className="text-red-600">Reject</Button></div>
      </div>
    </Card>)}{funds.length === 0 && <Card><p className="py-8 text-center text-sm text-fundinv-muted">No pending fund reviews.</p></Card>}</div>
  </div>;
}
