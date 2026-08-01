'use client';

import { useEffect, useState } from 'react';
import Card from '../../../components/Card';
import { api } from '../../../lib/api';

type Valuation = {
  id: number; fund_name: string; valuation_date: string; opening_assets: number;
  daily_pnl: number; closing_assets_before_flows: number; net_flow: number;
  closing_assets: number; units_outstanding: number; nav_per_unit: number;
  status: string; source: string; finalized_by_name: string; finalized_at: string | null; notes: string | null;
};

const money = (value: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(value);

export default function AdminValuationsPage() {
  const [rows, setRows] = useState<Valuation[]>([]);
  const [error, setError] = useState('');

  useEffect(() => {
    api.get<{ valuations: Valuation[] }>('/api/admin/valuations')
      .then((result) => setRows(result.valuations))
      .catch((err) => setError(err instanceof Error ? err.message : 'Unable to load valuation audit history'));
  }, []);

  return <div className="max-w-6xl mx-auto px-8 py-8 space-y-6">
    <div><h1 className="text-2xl font-semibold text-fundinv-primary">Fund Valuation Audit</h1><p className="text-sm text-fundinv-muted mt-1">Read-only oversight of Manager-finalized NAVs, P&amp;L and subsequent investor flows.</p></div>
    {error && <p className="text-sm text-red-600">{error}</p>}
    <Card title="Valuation ledger">
      <div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b"><th className="text-left py-2">Date / Fund</th><th className="text-right">Opening</th><th className="text-right">P&amp;L</th><th className="text-right">Before flows</th><th className="text-right">Net flows</th><th className="text-right">Closing</th><th className="text-right">Units / NAV</th><th className="text-left pl-4">Audit</th></tr></thead>
        <tbody>{rows.map((row) => <tr key={row.id} className="border-b last:border-0 align-top"><td className="py-3"><div>{row.valuation_date}</div><div className="text-xs text-fundinv-muted">{row.fund_name}</div></td><td className="text-right py-3">{money(row.opening_assets)}</td><td className={`text-right py-3 ${row.daily_pnl >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>{money(row.daily_pnl)}</td><td className="text-right py-3">{money(row.closing_assets_before_flows)}</td><td className="text-right py-3">{money(row.net_flow)}</td><td className="text-right py-3">{money(row.closing_assets)}</td><td className="text-right py-3"><div>{row.units_outstanding.toFixed(4)}</div><div className="text-xs text-fundinv-muted">${row.nav_per_unit.toFixed(8)}</div></td><td className="pl-4 py-3"><div className="capitalize">{row.source.replaceAll('_', ' ')}</div><div className="text-xs text-fundinv-muted">{row.finalized_by_name}</div>{row.notes && <div className="text-xs mt-1 max-w-48">{row.notes}</div>}</td></tr>)}</tbody>
      </table>{rows.length === 0 && !error && <p className="py-8 text-center text-sm text-fundinv-muted">No valuations recorded.</p>}</div>
    </Card>
  </div>;
}
