'use client';

import { useState, useEffect, useCallback } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';
import type { FundFlowEntry } from '../../../lib/types';

export default function OperationsFundFlowsPage() {
  const [flows, setFlows] = useState<FundFlowEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [flowType, setFlowType] = useState('');
  const [status, setStatus] = useState('');
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

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

  const handleAction = async (flowId: number, action: string) => {
    setActionLoading(flowId);
    setActionError(null);
    try {
      await api.post(`/api/admin/fund-flows/${flowId}/${action}`, {});
      fetchFlows(page, search, flowType, status);
    } catch (err) {
      const msg = (err as { message?: string }).message || 'Action failed';
      setActionError(msg);
    } finally {
      setActionLoading(null);
    }
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
      case 'awaiting_investor_payment': return 'text-purple-600 bg-purple-50';
      case 'pending_fund_transfer': return 'text-blue-600 bg-blue-50';
      case 'pending': return 'text-amber-600 bg-amber-50';
      case 'approved_pending_payment': return 'text-blue-600 bg-blue-50';
      case 'awaiting_payout_setup': return 'text-blue-600 bg-blue-50';
      case 'failed': return 'text-fundinv-danger bg-red-50';
      case 'rejected': return 'text-fundinv-danger bg-red-50';
      default: return 'text-fundinv-muted bg-fundinv-surface';
    }
  };

  const canApprove = (flow: FundFlowEntry) => flow.status === 'pending_ops_team' && flow.provider !== 'paynow_demo';
  const canVerifyPayNow = (flow: FundFlowEntry) => (
    flow.status === 'pending_ops_team' &&
    flow.provider === 'paynow_demo' &&
    flow.paid_amount !== null &&
    flow.paid_amount !== undefined
  );
  const canComplete = (s: string) => s === 'pending_fund_transfer';
  const canReject = (s: string) => ['awaiting_investor_payment', 'pending_ops_team', 'pending_fund_transfer', 'approved_pending_payment', 'awaiting_payout_setup', 'pending'].includes(s);

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-fundinv-primary">Fund Flows</h1>
          <p className="text-sm text-fundinv-muted mt-1">Review and process investor fund subscriptions and redemptions</p>
        </div>
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
              <option value="awaiting_investor_payment">Awaiting Investor Payment</option>
              <option value="pending_ops_team">Pending Ops Team</option>
               <option value="approved_pending_payment">Pending Payment</option>
               <option value="awaiting_payout_setup">Payout Setup Required</option>
              <option value="pending_fund_transfer">Pending Fund Transfer</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
              <option value="rejected">Rejected</option>
            </select>
          </div>
        </div>

        {actionError && (
          <div className="mb-4 px-4 py-2.5 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">
            {actionError}
          </div>
        )}

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
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Fund</th>
                    <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Requested</th>
                    <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Received</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Status</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Request ID</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Requested</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Processed</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Processed By</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Notes</th>
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Actions</th>
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
                      <td className="py-3 px-2 text-sm text-fundinv-primary">{flow.fund_name || 'Legacy / unallocated'}</td>
                      <td className="py-3 px-2 text-right font-mono text-fundinv-primary">
                        {formatAmount(flow.amount)}
                      </td>
                      <td className={`py-3 px-2 text-right font-mono ${
                        flow.paid_amount == null
                          ? 'text-fundinv-muted'
                          : Math.abs(flow.paid_amount - flow.amount) < 0.001
                            ? 'text-fundinv-success'
                            : 'text-red-600 font-semibold'
                      }`}>
                        {flow.paid_amount == null ? '—' : formatAmount(flow.paid_amount)}
                        {flow.payment_received_at && <div className="text-[10px] font-sans text-fundinv-muted">{formatDate(flow.payment_received_at)}</div>}
                      </td>
                      <td className="py-3 px-2">
                        <span className={`px-2 py-1 text-xs font-medium rounded capitalize ${statusColor(flow.status)}`}>
                          {flow.status.replace(/_/g, ' ')}
                        </span>
                        {flow.status_message && <p className="mt-1 max-w-[220px] text-xs text-fundinv-muted normal-case">{flow.status_message}</p>}
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
                      <td className="py-3 px-2 text-xs text-fundinv-muted max-w-[150px] truncate">{flow.notes || '—'}</td>
                      <td className="py-3 px-6">
                        <div className="flex gap-1">
                          {canVerifyPayNow(flow) && (
                            <Button
                              onClick={() => handleAction(flow.id, 'verify-complete')}
                              disabled={actionLoading === flow.id}
                              className="px-2 py-1 text-xs whitespace-nowrap"
                            >
                              {actionLoading === flow.id ? '...' : 'Verify & Complete'}
                            </Button>
                          )}
                          {canApprove(flow) && (
                            <Button
                              variant="secondary"
                              onClick={() => handleAction(flow.id, 'approve')}
                              disabled={actionLoading === flow.id}
                              className="px-2 py-1 text-xs"
                            >
                              {actionLoading === flow.id ? '...' : 'Approve'}
                            </Button>
                          )}
                          {canComplete(flow.status) && (
                            <Button
                              onClick={() => handleAction(flow.id, 'complete')}
                              disabled={actionLoading === flow.id}
                              className="px-2 py-1 text-xs"
                            >
                              {actionLoading === flow.id ? '...' : 'Complete'}
                            </Button>
                          )}
                          {flow.status === 'awaiting_payout_setup' && (
                            <Button
                              onClick={() => handleAction(flow.id, 'start-payout')}
                              disabled={actionLoading === flow.id}
                              className="px-2 py-1 text-xs"
                            >
                              {actionLoading === flow.id ? '...' : 'Start Payout'}
                            </Button>
                          )}
                          {flow.flow_type === 'withdrawal' && flow.status === 'failed' && (
                            <Button
                              onClick={() => handleAction(flow.id, 'start-payout')}
                              disabled={actionLoading === flow.id}
                              className="px-2 py-1 text-xs"
                            >
                              Retry Payout
                            </Button>
                          )}
                          {canReject(flow.status) && (
                            <Button
                              variant="secondary"
                              onClick={() => handleAction(flow.id, 'reject')}
                              disabled={actionLoading === flow.id}
                              className="px-2 py-1 text-xs text-red-600 border-red-300 hover:bg-red-50"
                            >
                              {actionLoading === flow.id ? '...' : 'Reject'}
                            </Button>
                          )}
                          {(flow.status === 'completed' || flow.status === 'failed' || flow.status === 'rejected') && (
                            <span className="text-xs text-fundinv-muted">—</span>
                          )}
                        </div>
                      </td>
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
