'use client';

import { useState, useEffect, useCallback } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';
import type { FundFlowEntry } from '../../../lib/types';

export default function FundFlowsPage() {
  const [flows, setFlows] = useState<FundFlowEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [flowType, setFlowType] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  const fetchFlows = useCallback(async (pageNum: number, searchTerm: string, typeFilter: string, statusFilter: string) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(pageNum),
        page_size: '15',
      });
      if (searchTerm) params.set('search', searchTerm);
      if (typeFilter) params.set('flow_type', typeFilter);
      if (statusFilter) params.set('status', statusFilter);

      const data = await api.get<{ flows: FundFlowEntry[]; total: number; page: number; page_size: number; total_pages: number }>(`/api/admin/fund-flows?${params}`);
      setFlows(data.flows);
      setTotalPages(data.total_pages);
      setTotal(data.total);
      setPage(data.page);
    } catch {
      setFlows([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchFlows(1, search, flowType, status);
  }, [fetchFlows, search, flowType, status]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setPage(1);
    setSearch(searchInput);
  };

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || newPage > totalPages) return;
    fetchFlows(newPage, search, flowType, status);
  };

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(amount);
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

  const statusColor = (s: string) => {
    switch (s) {
      case 'completed': return 'text-fundinv-success bg-emerald-50';
      case 'pending_ops_team': return 'text-amber-600 bg-amber-50';
      case 'pending_fund_transfer': return 'text-blue-600 bg-blue-50';
      case 'pending': return 'text-amber-600 bg-amber-50';
      case 'failed': return 'text-fundinv-danger bg-red-50';
      case 'rejected': return 'text-fundinv-danger bg-red-50';
      default: return 'text-fundinv-muted bg-fundinv-surface';
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-fundinv-primary">Fund Flows</h1>
        <p className="text-sm text-fundinv-muted mt-1">Audit fund subscription and redemption requests (read-only)</p>
      </div>

      <Card>
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          <form onSubmit={handleSearch} className="flex-1 flex gap-2">
            <div className="flex-1">
              <Input
                placeholder="Search by email, name, or request ID..."
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
              />
            </div>
            <Button type="submit" variant="secondary" className="px-4">Search</Button>
          </form>

          <div className="flex gap-2">
            <select
              value={flowType}
              onChange={(e) => { setFlowType(e.target.value); setPage(1); }}
              className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
            >
              <option value="">All Types</option>
              <option value="deposit">Subscription</option>
              <option value="withdrawal">Redemption</option>
            </select>

            <select
              value={status}
              onChange={(e) => { setStatus(e.target.value); setPage(1); }}
              className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
            >
              <option value="">All Status</option>
              <option value="pending_ops_team">Pending Ops Team</option>
              <option value="pending">Pending Payment</option>
              <option value="pending_fund_transfer">Pending Fund Transfer</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="py-12 text-center text-sm text-fundinv-muted">Loading fund flows...</div>
        ) : flows.length === 0 ? (
          <div className="py-12 text-center text-sm text-fundinv-muted">No fund flows found.</div>
        ) : (
          <>
            <div className="overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-fundinv-border">
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Investor</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Type</th>
                    <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Amount</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Status</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Request ID</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Requested</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Processed</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Processed By</th>
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {flows.map((flow) => (
                    <tr key={flow.id} className="border-b border-fundinv-border last:border-0">
                      <td className="py-3 px-6">
                        <div className="text-fundinv-primary">{flow.investor_name || '—'}</div>
                        <div className="text-xs text-fundinv-muted">{flow.investor_email || '—'}</div>
                      </td>
                      <td className="py-3 px-2">
                        <span className={`px-2 py-1 text-xs font-medium rounded capitalize ${
                          flow.flow_type === 'deposit' ? 'text-fundinv-accent bg-blue-50' : 'text-fundinv-warning bg-amber-50'
                        }`}>
                          {flow.flow_type === 'deposit' ? 'subscription' : flow.flow_type === 'withdrawal' ? 'redemption' : flow.flow_type}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-right font-mono text-fundinv-primary">
                        {formatAmount(flow.amount)}
                      </td>
                      <td className="py-3 px-2">
                        <span className={`px-2 py-1 text-xs font-medium rounded capitalize ${statusColor(flow.status)}`}>
                          {flow.status.replace(/_/g, ' ')}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted font-mono">{flow.request_id}</td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted whitespace-nowrap">{formatDate(flow.requested_at)}</td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted whitespace-nowrap">{formatDate(flow.processed_at)}</td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted">
                        {flow.processed_by_name ? (
                          <>
                            <div>{flow.processed_by_name}</div>
                            <div>{flow.processed_by_email}</div>
                          </>
                        ) : '—'}
                      </td>
                      <td className="py-3 px-6 text-xs text-fundinv-muted max-w-[150px] truncate">{flow.notes || '—'}</td>
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
