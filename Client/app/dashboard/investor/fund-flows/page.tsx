'use client';

import { useState, useEffect, useCallback } from 'react';
import Image from 'next/image';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import { api } from '../../../lib/api';
import type { FundFlowEntry } from '../../../lib/types';

export default function InvestorFundFlowsPage() {
  const [flows, setFlows] = useState<FundFlowEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [paymentLoading, setPaymentLoading] = useState<number | null>(null);
  const [paymentError, setPaymentError] = useState<string | null>(null);

  const fetchFlows = useCallback(async (pageNum: number) => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: String(pageNum),
        page_size: '15',
      });
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
    fetchFlows(1);
  }, [fetchFlows]);

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || newPage > totalPages) return;
    fetchFlows(newPage);
  };

  const simulatePayNow = async (flowId: number) => {
    setPaymentLoading(flowId);
    setPaymentError(null);
    try {
      await api.post(`/api/funds/fund-flows/${flowId}/simulate-paynow`, {});
      await fetchFlows(page);
    } catch (err) {
      setPaymentError((err as { message?: string }).message || 'Could not record demo PayNow payment');
    } finally {
      setPaymentLoading(null);
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
      case 'awaiting_investor_payment': return 'text-purple-600 bg-purple-50';
      case 'approved_pending_payment': return 'text-blue-600 bg-blue-50';
      case 'awaiting_payout_setup': return 'text-blue-600 bg-blue-50';
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
        <p className="text-sm text-fundinv-muted mt-1">Track your fund subscription and redemption requests</p>
      </div>

      <Card>
        {paymentError && <div className="mb-4 px-4 py-2.5 bg-red-50 border border-red-200 rounded-md text-sm text-red-700">{paymentError}</div>}
        {loading ? (
          <div className="py-12 text-center text-sm text-fundinv-muted">Loading fund flows...</div>
        ) : flows.length === 0 ? (
          <div className="py-12 text-center text-sm text-fundinv-muted">
            <p className="mb-2">No fund flow requests yet.</p>
            <p className="text-xs">Use the Top Up or Withdraw buttons on your Portfolio page to get started.</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-fundinv-border">
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Type</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Fund</th>
                    <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Amount</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Status</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Request ID</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Requested</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Processed</th>
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Notes</th>
                  </tr>
                </thead>
                <tbody>
                  {flows.map((flow) => (
                    <tr key={flow.id} className="border-b border-fundinv-border last:border-0">
                      <td className="py-3 px-6">
                        <span className={`px-2 py-1 text-xs font-medium rounded capitalize ${
                          flow.flow_type === 'deposit' ? 'text-fundinv-accent bg-blue-50' : 'text-fundinv-warning bg-amber-50'
                        }`}>
                          {flow.flow_type === 'deposit' ? 'subscription' : flow.flow_type === 'withdrawal' ? 'redemption' : flow.flow_type}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-sm text-fundinv-primary">
                        {flow.fund_name || 'Legacy / unallocated'}
                      </td>
                      <td className="py-3 px-2 text-right font-mono text-fundinv-primary">
                        {formatAmount(flow.amount)}
                      </td>
                      <td className="py-3 px-2">
                        <span className={`px-2 py-1 text-xs font-medium rounded capitalize ${statusColor(flow.status)}`}>
                          {flow.status.replace(/_/g, ' ')}
                        </span>
                        {flow.status_message && <p className="mt-1 max-w-[220px] text-xs text-fundinv-muted normal-case">{flow.status_message}</p>}
                        {flow.next_action === 'investor_payment' && flow.payment_url && (
                          <div className="mt-2 rounded-md border border-fundinv-border bg-white p-2 text-center">
                            {flow.paynow_qr_data_url && (
                              <Image
                                src={flow.paynow_qr_data_url}
                                alt={`Demo PayNow QR for ${flow.request_id}`}
                                width={128}
                                height={128}
                                unoptimized
                                className="mx-auto"
                              />
                            )}
                            <p className="mt-1 text-xs font-medium text-fundinv-primary">Fixed: {formatAmount(flow.amount)}</p>
                            <Button
                              onClick={() => simulatePayNow(flow.id)}
                              disabled={paymentLoading === flow.id}
                              className="mt-2 px-2 py-1 text-xs"
                            >
                              {paymentLoading === flow.id ? 'Recording...' : 'Simulate Payment'}
                            </Button>
                          </div>
                        )}
                      </td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted font-mono">{flow.request_id}</td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted whitespace-nowrap">{formatDate(flow.requested_at)}</td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted whitespace-nowrap">{formatDate(flow.processed_at)}</td>
                      <td className="py-3 px-6 text-xs text-fundinv-muted max-w-[200px] truncate">{flow.notes || '—'}</td>
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
