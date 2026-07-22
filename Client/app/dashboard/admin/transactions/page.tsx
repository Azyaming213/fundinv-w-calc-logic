'use client';

import { useState, useEffect, useCallback } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';
import type { AdminTransaction } from '../../../lib/types';

export default function TransactionsPage() {
  const [txns, setTxns] = useState<AdminTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [tradeType, setTradeType] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const fetchTxns = useCallback(async (pageNum: number, searchTerm: string, typeFilter: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(pageNum),
        page_size: '15',
      });
      if (searchTerm) params.set('search', searchTerm);
      if (typeFilter) params.set('trade_type', typeFilter);

      const data = await api.get<{ transactions: AdminTransaction[]; total: number; page: number; page_size: number; total_pages: number }>(`/api/admin/transactions?${params}`);
      setTxns(data.transactions);
      setTotalPages(data.total_pages);
      setTotal(data.total);
      setPage(data.page);
    } catch {
      setTxns([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTxns(1, search, tradeType);
  }, [fetchTxns, search, tradeType]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  };

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || newPage > totalPages) return;
    fetchTxns(newPage, search, tradeType);
  };

  const fmt = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);

  const pnlColor = (n: number) => {
    if (n > 0) return 'text-fundinv-success';
    if (n < 0) return 'text-fundinv-danger';
    return 'text-fundinv-muted';
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '—';
    return new Date(dateStr).toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-fundinv-primary">Investment Transactions</h1>
        <p className="text-sm text-fundinv-muted mt-1">All trade executions across investor accounts</p>
      </div>

      <Card>
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <form onSubmit={handleSearch} className="flex-1 flex gap-2">
            <div className="flex-1">
              <Input
                placeholder="Search by ticket, symbol, investor..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
            <Button type="submit" variant="secondary" className="px-4">Search</Button>
          </form>

          <select
            value={tradeType}
            onChange={(e) => { setTradeType(e.target.value); setPage(1); }}
            className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
          >
            <option value="">All Types</option>
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
        </div>

        {loading ? (
          <div className="py-12 text-center text-sm text-fundinv-muted">Loading transactions...</div>
        ) : txns.length === 0 ? (
          <div className="py-12 text-center text-sm text-fundinv-muted">No transactions found.</div>
        ) : (
          <>
            <div className="overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-fundinv-border">
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Investor</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Ticket</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Type</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Symbol</th>
                    <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Volume</th>
                    <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Price</th>
                    <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Net P&L</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {txns.map((t) => (
                    <tr key={t.id} className="border-b border-fundinv-border last:border-0">
                      <td className="py-3 px-6">
                        <div className="text-fundinv-primary">{t.investor_name || '—'}</div>
                        <div className="text-xs text-fundinv-muted">{t.investor_email || '—'}</div>
                      </td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted font-mono">{t.ticket}</td>
                      <td className="py-3 px-2">
                        <span className={`px-2 py-1 text-xs font-medium rounded uppercase ${
                          t.trade_type === 'buy' ? 'text-fundinv-success bg-emerald-50' : 'text-fundinv-danger bg-red-50'
                        }`}>
                          {t.trade_type}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-sm font-medium text-fundinv-primary">{t.symbol}</td>
                      <td className="py-3 px-2 text-right font-mono text-fundinv-muted">{t.volume}</td>
                      <td className="py-3 px-2 text-right font-mono text-fundinv-muted">{t.price}</td>
                      <td className={`py-3 px-2 text-right font-mono font-medium ${pnlColor(t.net_pnl)}`}>
                        {fmt(t.net_pnl)}
                      </td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted whitespace-nowrap">{formatDate(t.trade_time)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-fundinv-border">
                <p className="text-xs text-fundinv-muted">
                  Showing {(page - 1) * 15 + 1}–{Math.min(page * 15, total)} of {total}
                </p>
                <div className="flex gap-2">
                  <Button variant="secondary" onClick={() => handlePageChange(page - 1)} disabled={page <= 1} className="px-3 py-1.5 text-xs">
                    Previous
                  </Button>
                  <Button variant="secondary" onClick={() => handlePageChange(page + 1)} disabled={page >= totalPages} className="px-3 py-1.5 text-xs">
                    Next
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}
