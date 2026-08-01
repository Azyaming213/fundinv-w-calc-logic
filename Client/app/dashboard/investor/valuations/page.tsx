'use client';

import { useEffect, useState } from 'react';
import Card from '../../../components/Card';
import { api } from '../../../lib/api';

type Allocation = {
  id: number; fund_name: string; valuation_date: string; opening_value: number;
  opening_share_pct: number; allocated_pnl: number; closing_value_before_flows: number;
  net_flow: number; closing_value: number; closing_units: number; nav_per_unit: number;
  closing_share_pct: number; valuation_status: string; valuation_source: string;
};

const money = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);

export default function InvestorValuationsPage() {
  const [rows, setRows] = useState<Allocation[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get<{ valuations: Allocation[] }>('/api/portfolio/valuation-history')
      .then((result) => setRows(result.valuations))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load P&L allocations'));
  }, []);

  return <div className="max-w-6xl mx-auto px-8 py-8 space-y-6">
    <div><h1 className="text-2xl font-semibold text-fundinv-primary">My Fund P&amp;L Allocations</h1><p className="text-sm text-fundinv-muted mt-1">A transparent daily breakdown of how each fund&apos;s return changes your units&apos; value.</p></div>
    <Card title="How each daily value is calculated"><div className="grid md:grid-cols-3 gap-4 text-sm"><div><p className="font-medium">1. Your P&amp;L share</p><p className="text-fundinv-muted mt-1">Fund P&amp;L × your opening units ÷ total opening fund units.</p></div><div><p className="font-medium">2. Value before flows</p><p className="text-fundinv-muted mt-1">Opening value + your allocated P&amp;L.</p></div><div><p className="font-medium">3. Closing value</p><p className="text-fundinv-muted mt-1">Value before flows + subscriptions − redemptions. P&amp;L itself never creates units.</p></div></div></Card>
    {error && <p className="text-sm text-red-600">{error}</p>}
    <Card title="Daily allocation ledger"><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b"><th className="text-left py-2">Date / Fund</th><th className="text-right">Opening value</th><th className="text-right">Opening share</th><th className="text-right">Allocated P&amp;L</th><th className="text-right">Before flows</th><th className="text-right">Net flow</th><th className="text-right">Closing value</th><th className="text-right">Units / NAV</th></tr></thead>
      <tbody>{rows.map((row) => <tr key={row.id} className="border-b last:border-0 align-top"><td className="py-3"><div>{row.valuation_date}</div><div className="text-xs text-fundinv-muted">{row.fund_name}</div></td><td className="text-right py-3">{money(row.opening_value)}</td><td className="text-right py-3">{row.opening_share_pct.toFixed(4)}%</td><td className={`text-right py-3 ${row.allocated_pnl >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{money(row.allocated_pnl)}</td><td className="text-right py-3">{money(row.closing_value_before_flows)}</td><td className="text-right py-3">{money(row.net_flow)}</td><td className="text-right py-3 font-medium">{money(row.closing_value)}</td><td className="text-right py-3"><div>{row.closing_units.toFixed(4)}</div><div className="text-xs text-fundinv-muted">${row.nav_per_unit.toFixed(8)}</div></td></tr>)}</tbody>
    </table>{rows.length === 0 && !error && <p className="py-8 text-center text-sm text-fundinv-muted">Your first allocation appears after a Manager finalizes a valuation for a fund you own.</p>}</div></Card>
  </div>;
}
