'use client';

import { useCallback, useEffect, useState } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';

type Fund = { id: number; name: string; fund_type: string; is_active: boolean; review_status: string };
type Allocation = { investor_id: number; investment_account_ids: number[]; investor_name: string; investor_email: string; units: number; opening_share_pct: number; allocated_pnl: number; opening_value: number; closing_value_before_flows: number };
type Preview = { fund_id: number; fund_name: string; valuation_date: string; previous_valuation_date: string | null; opening_assets: number; opening_units: number; opening_nav_per_unit: number; daily_pnl: number; closing_assets_before_flows: number; closing_assets: number; closing_units: number; nav_per_unit: number; allocated_pnl_total: number; external_ownership_pnl: number; allocations: Allocation[]; status?: string };
type History = { id: number; fund_name: string; valuation_date: string; opening_assets: number; daily_pnl: number; net_flow: number; closing_assets: number; units_outstanding: number; nav_per_unit: number; source: string; finalized_by_name: string; notes: string | null };

const fmt = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);

export default function ManagerValuationsPage() {
  const [funds, setFunds] = useState<Fund[]>([]);
  const [history, setHistory] = useState<History[]>([]);
  const [fundId, setFundId] = useState('');
  const [valuationDate, setValuationDate] = useState(new Date().toISOString().slice(0, 10));
  const [dailyPnl, setDailyPnl] = useState('');
  const [notes, setNotes] = useState('');
  const [preview, setPreview] = useState<Preview | null>(null);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    try {
      const [fundData, valuationData] = await Promise.all([
        api.get<{ funds: Fund[] }>('/api/manager/funds'),
        api.get<{ valuations: History[] }>('/api/manager/valuations'),
      ]);
      const eligible = fundData.funds.filter((fund) => fund.fund_type !== 'stock' && fund.is_active && fund.review_status === 'approved');
      setFunds(eligible);
      setFundId((current) => current || String(eligible[0]?.id || ''));
      setHistory(valuationData.valuations);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load valuations');
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function submit(mode: 'preview' | 'finalize') {
    setLoading(true); setError(''); setMessage('');
    try {
      const body = { fund_id: Number(fundId), valuation_date: valuationDate, daily_pnl: Number(dailyPnl), notes: notes || null };
      const result = await api.post<Preview>(`/api/manager/valuations/${mode}`, body);
      setPreview(result);
      if (mode === 'finalize') {
        setMessage(`Finalized ${result.fund_name} at NAV ${result.nav_per_unit.toFixed(8)}.`);
        await load();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : `Unable to ${mode} valuation`);
    } finally { setLoading(false); }
  }

  return <div className="max-w-6xl mx-auto px-8 py-8 space-y-6">
    <div><h1 className="text-2xl font-semibold text-fundinv-primary">Daily Fund Valuation</h1><p className="text-sm text-fundinv-muted mt-1">Apply fund-level P&amp;L before Operations settles the day&apos;s subscriptions and redemptions.</p></div>
    <Card title="Valuation input">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div><label className="text-sm font-medium text-fundinv-primary">Fund</label><select value={fundId} onChange={(e) => { setFundId(e.target.value); setPreview(null); }} className="mt-1.5 w-full px-3 py-2 border border-fundinv-border rounded-md bg-white text-sm"><option value="">Select fund</option>{funds.map((fund) => <option key={fund.id} value={fund.id}>{fund.name}</option>)}</select></div>
        <Input label="Valuation date" type="date" value={valuationDate} onChange={(e) => { setValuationDate(e.target.value); setPreview(null); }} />
        <Input label="Daily fund P&L (USD)" type="number" step="0.01" value={dailyPnl} onChange={(e) => { setDailyPnl(e.target.value); setPreview(null); }} placeholder="e.g. 500 or -125" />
      </div>
      <div className="mt-4"><Input label="Audit note (optional)" value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Reason or source for today’s P&L" /></div>
      <div className="mt-4 flex gap-2"><Button variant="secondary" disabled={loading || !fundId || dailyPnl === ''} onClick={() => submit('preview')}>{loading ? 'Calculating…' : 'Preview calculation'}</Button><Button disabled={loading || !preview} onClick={() => submit('finalize')}>Finalize valuation</Button></div>
      {error && <p className="mt-3 text-sm text-red-600">{error}</p>}{message && <p className="mt-3 text-sm text-emerald-700">{message}</p>}
    </Card>

    {preview && <>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card><p className="text-xs text-fundinv-muted">Opening assets</p><p className="text-xl font-semibold">{fmt(preview.opening_assets)}</p></Card>
        <Card><p className="text-xs text-fundinv-muted">Daily P&amp;L</p><p className={`text-xl font-semibold ${preview.daily_pnl >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{fmt(preview.daily_pnl)}</p></Card>
        <Card><p className="text-xs text-fundinv-muted">Closing before flows</p><p className="text-xl font-semibold">{fmt(preview.closing_assets_before_flows)}</p></Card>
        <Card><p className="text-xs text-fundinv-muted">NAV per unit</p><p className="text-xl font-semibold">${preview.nav_per_unit.toFixed(8)}</p></Card>
      </div>
      <Card title="Investor P&L allocation preview">
        <p className="text-xs text-fundinv-muted mb-3">Allocated using opening units ÷ {preview.opening_units.toFixed(4)} opening fund units. Units do not change because of P&amp;L.</p>
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b"><th className="text-left py-2">Investor</th><th className="text-right">Opening units</th><th className="text-right">Opening share</th><th className="text-right">Opening value</th><th className="text-right">Allocated P&amp;L</th><th className="text-right">Value before flows</th></tr></thead><tbody>{preview.allocations.map((row) => <tr key={row.investor_id} className="border-b last:border-0"><td className="py-2"><div>{row.investor_name}</div><div className="text-xs text-fundinv-muted">{row.investor_email}</div></td><td className="text-right">{row.units.toFixed(4)}</td><td className="text-right">{row.opening_share_pct.toFixed(4)}%</td><td className="text-right">{fmt(row.opening_value)}</td><td className={`text-right ${row.allocated_pnl >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{fmt(row.allocated_pnl)}</td><td className="text-right">{fmt(row.closing_value_before_flows)}</td></tr>)}</tbody></table></div>
        {Math.abs(preview.external_ownership_pnl) > 0.005 && <p className="mt-3 text-xs text-amber-700">{fmt(preview.external_ownership_pnl)} belongs to ownership represented outside the portal dataset and is not assigned to a portal Investor.</p>}
      </Card>
    </>}

    <Card title="Finalized valuation history"><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b"><th className="text-left py-2">Date / Fund</th><th className="text-right">Opening</th><th className="text-right">P&amp;L</th><th className="text-right">Flows</th><th className="text-right">Closing</th><th className="text-right">NAV</th><th className="text-left pl-4">Source</th></tr></thead><tbody>{history.map((row) => <tr key={row.id} className="border-b last:border-0"><td className="py-2"><div>{row.valuation_date}</div><div className="text-xs text-fundinv-muted">{row.fund_name}</div></td><td className="text-right">{fmt(row.opening_assets)}</td><td className={`text-right ${row.daily_pnl >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{fmt(row.daily_pnl)}</td><td className="text-right">{fmt(row.net_flow)}</td><td className="text-right">{fmt(row.closing_assets)}</td><td className="text-right">${row.nav_per_unit.toFixed(8)}</td><td className="pl-4"><div>{row.source.replaceAll('_', ' ')}</div><div className="text-xs text-fundinv-muted">{row.finalized_by_name}</div></td></tr>)}</tbody></table></div></Card>
  </div>;
}
