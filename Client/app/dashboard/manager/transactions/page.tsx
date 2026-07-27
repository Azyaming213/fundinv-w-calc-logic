'use client';

import { useState, useEffect, useCallback } from 'react';
import Card from '../../../components/Card';
import Input from '../../../components/Input';
import Button from '../../../components/Button';
import { api, API_BASE } from '../../../lib/api';
import type { ManagerOrder } from '../../../lib/types';

export default function ManagerTransactionsPage() {
  const [orders, setOrders] = useState<ManagerOrder[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [side, setSide] = useState('');
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [exporting, setExporting] = useState(false);
  const pageSize = 20;

  const fetchOrders = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      params.set('page', String(page));
      params.set('page_size', String(pageSize));
      if (search) params.set('search', search);
      if (side) params.set('side', side);
      const data = await api.get<{ orders: ManagerOrder[]; total: number }>(`/api/manager/transactions?${params}`);
      setOrders(data.orders || []);
      setTotal(data.total || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, search, side]);

  useEffect(() => {
    fetchOrders();
  }, [fetchOrders]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const resp = await fetch(`${API_BASE}/api/manager/transactions/export`, {
        credentials: 'include',
      });
      if (!resp.ok) throw new Error('Export failed');
      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `manager_transactions.csv`;
      a.click();
      window.URL.revokeObjectURL(url);
    } catch {
      // silent
    } finally {
      setExporting(false);
    }
  };

  const totalPages = Math.ceil(total / pageSize);

  const fmt = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-semibold text-fundinv-primary">My Transactions</h1>
          <p className="text-sm text-fundinv-muted mt-1">{total} trade{total !== 1 ? 's' : ''} executed</p>
        </div>
        <Button variant="secondary" onClick={handleExport} disabled={exporting}>
          {exporting ? 'Exporting...' : 'Export CSV'}
        </Button>
      </div>

      <Card className="mb-6">
        <div className="flex flex-wrap items-end gap-3">
          <div className="flex-1 min-w-[150px]">
            <Input placeholder="Search by symbol..." value={search}
              onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
          </div>
          <select value={side} onChange={(e) => { setSide(e.target.value); setPage(1); }}
            className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent">
            <option value="">All Sides</option>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </div>
      </Card>

      {loading ? (
        <div className="py-16 text-center text-sm text-fundinv-muted">Loading transactions...</div>
      ) : orders.length === 0 ? (
        <Card><div className="py-8 text-center text-sm text-fundinv-muted">No transactions yet.</div></Card>
      ) : (
        <Card>
          <div className="overflow-x-auto -mx-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-fundinv-border">
                  <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Date</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Investor</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Symbol</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Side</th>
                  <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Amount</th>
                  <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Filled Qty</th>
                  <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Filled Price</th>
                  <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Status</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((o) => (
                  <tr key={o.id} className="border-b border-fundinv-border last:border-0 hover:bg-fundinv-surface/50">
                    <td className="py-3 px-6 text-xs text-fundinv-muted">{o.created_at ? new Date(o.created_at).toLocaleString() : '—'}</td>
                    <td className="py-3 px-2">
                      <p className="font-medium text-fundinv-primary text-xs">{o.investor_name}</p>
                      <p className="text-[10px] text-fundinv-muted">{o.investor_email}</p>
                    </td>
                    <td className="py-3 px-2 font-mono font-semibold text-fundinv-primary">{o.symbol}</td>
                    <td className="py-3 px-2">
                      <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded uppercase ${o.side === 'buy' ? 'text-emerald-600 bg-emerald-50' : 'text-red-600 bg-red-50'}`}>
                        {o.side}
                      </span>
                    </td>
                    <td className="py-3 px-2 text-right font-mono text-fundinv-primary">{fmt(o.amount)}</td>
                    <td className="py-3 px-2 text-right font-mono text-fundinv-muted">{o.filled_qty != null ? o.filled_qty.toFixed(4) : '—'}</td>
                    <td className="py-3 px-2 text-right font-mono text-fundinv-muted">{o.filled_price != null ? fmt(o.filled_price) : '—'}</td>
                    <td className="py-3 px-6">
                      <span className={`px-2 py-0.5 text-[10px] font-medium rounded-full ${o.status === 'filled' || o.status === 'completed' ? 'bg-green-50 text-green-700' : o.status === 'rejected' ? 'bg-red-50 text-red-700' : 'bg-amber-50 text-amber-700'}`}>
                        {o.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {totalPages > 1 && (
            <div className="flex items-center justify-between px-6 py-3 border-t border-fundinv-border">
              <p className="text-xs text-fundinv-muted">Page {page} of {totalPages}</p>
              <div className="flex gap-2">
                <Button variant="secondary" className="text-xs py-1 px-3" disabled={page <= 1} onClick={() => setPage(p => p - 1)}>Prev</Button>
                <Button variant="secondary" className="text-xs py-1 px-3" disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>Next</Button>
              </div>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
