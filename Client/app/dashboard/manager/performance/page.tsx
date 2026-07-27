'use client';

import { useEffect, useState } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';

type Driver = { fund_id: number; fund_name: string; ticker: string | null; market_value: number; weight_pct: number; return_pct: number; contribution_pct: number };
type Analysis = { start_date: string; end_date: string; portfolio_value: number; portfolio_return_pct: number; drivers: Driver[] };
type Scenario = { hypothetical_return_pct: number; drivers: Driver[] };

export default function PerformanceAnalysisPage() {
  const now = new Date();
  const [start, setStart] = useState(() => new Date(now.getTime() - 30 * 86400000).toISOString().slice(0, 10));
  const [end, setEnd] = useState(() => now.toISOString().slice(0, 10));
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [weights, setWeights] = useState<Record<number, number>>({});
  const [scenario, setScenario] = useState<Scenario | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const load = async () => {
    setLoading(true); setError(null); setScenario(null);
    try {
      const data = await api.get<Analysis>(`/api/manager/performance-analysis?start_date=${start}T00:00:00Z&end_date=${end}T23:59:59Z`);
      setAnalysis(data);
      setWeights(Object.fromEntries(data.drivers.map((row) => [row.fund_id, Number(row.weight_pct.toFixed(2))])));
    } catch (err) { setError((err as { message?: string }).message || 'Unable to load performance analysis'); }
    finally { setLoading(false); }
  };

  useEffect(() => { load(); /* initial period */ }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const runScenario = async () => {
    if (!analysis) return;
    const total = Object.values(weights).reduce((sum, value) => sum + Number(value || 0), 0);
    if (Math.abs(total - 100) > 0.01) { setError(`Allocation must total 100% (currently ${total.toFixed(2)}%).`); return; }
    setLoading(true); setError(null);
    try {
      setScenario(await api.post<Scenario>('/api/manager/performance-analysis/what-if', {
        start_date: `${start}T00:00:00Z`, end_date: `${end}T23:59:59Z`,
        allocations: analysis.drivers.map((row) => ({ fund_id: row.fund_id, weight_pct: Number(weights[row.fund_id] || 0) })),
      }));
    } catch (err) { setError((err as { message?: string }).message || 'Unable to run scenario'); }
    finally { setLoading(false); }
  };

  const fmt = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);
  const tone = (value: number) => value > 0 ? 'text-fundinv-success' : value < 0 ? 'text-fundinv-danger' : 'text-fundinv-muted';

  return <div className="max-w-6xl mx-auto px-8 py-8">
    <h1 className="text-2xl font-semibold text-fundinv-primary">Performance attribution</h1>
    <p className="text-sm text-fundinv-muted mt-1 mb-6">Review return drivers and test alternative fund allocations.</p>
    <Card className="mb-6">
      <div className="flex flex-wrap items-end gap-3">
        <Input label="Start date" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
        <Input label="End date" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
        <Button onClick={load} disabled={loading}>{loading ? 'Loading…' : 'Refresh analysis'}</Button>
      </div>
    </Card>
    {error && <p className="mb-4 text-sm text-fundinv-danger">{error}</p>}
    {analysis && <>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card title="Managed value"><p className="text-2xl font-semibold">{fmt(analysis.portfolio_value)}</p></Card>
        <Card title="Actual weighted return"><p className={`text-2xl font-semibold ${tone(analysis.portfolio_return_pct)}`}>{analysis.portfolio_return_pct.toFixed(2)}%</p></Card>
        <Card title="What-if return"><p className={`text-2xl font-semibold ${tone(scenario?.hypothetical_return_pct || 0)}`}>{scenario ? `${scenario.hypothetical_return_pct.toFixed(2)}%` : '—'}</p></Card>
      </div>
      <Card title="Return drivers and scenario weights">
        <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b"><th className="text-left py-2">Fund</th><th className="text-right">Value</th><th className="text-right">Actual weight</th><th className="text-right">Fund return</th><th className="text-right">Contribution</th><th className="text-right">What-if weight</th></tr></thead><tbody>
          {analysis.drivers.map((row) => <tr key={row.fund_id} className="border-b border-fundinv-border"><td className="py-3">{row.fund_name} {row.ticker && `(${row.ticker})`}</td><td className="text-right">{fmt(row.market_value)}</td><td className="text-right">{row.weight_pct.toFixed(2)}%</td><td className={`text-right ${tone(row.return_pct)}`}>{row.return_pct.toFixed(2)}%</td><td className={`text-right ${tone(row.contribution_pct)}`}>{row.contribution_pct.toFixed(2)}%</td><td className="text-right"><input type="number" min="0" max="100" step="0.01" value={weights[row.fund_id] ?? 0} onChange={(e) => setWeights({ ...weights, [row.fund_id]: Number(e.target.value) })} className="w-24 px-2 py-1 border rounded text-right" /></td></tr>)}
        </tbody></table></div>
        <div className="mt-4 flex items-center justify-between"><p className="text-xs text-fundinv-muted">What-if weights must total 100%.</p><Button onClick={runScenario} disabled={loading || analysis.drivers.length === 0}>Run what-if</Button></div>
      </Card>
    </>}
  </div>;
}
