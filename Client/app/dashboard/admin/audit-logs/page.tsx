'use client';

import { useState, useEffect } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import { api } from '../../../lib/api';
import type { AuditLogEntry } from '../../../lib/types';

export default function AdminAuditLogsPage() {
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalLogs, setTotalLogs] = useState(0);

  const fetchLogs = async (pageNum: number) => {
    setLoading(true);
    try {
      const data = await api.get<{ logs: AuditLogEntry[]; total: number; page: number; page_size: number; total_pages: number }>(`/api/admin/audit-logs?page=${pageNum}&page_size=20`);
      setLogs(data.logs);
      setTotalPages(data.total_pages);
      setTotalLogs(data.total);
      setPage(data.page);
    } catch {
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs(1);
  }, []);

  const handlePageChange = (newPage: number) => {
    if (newPage < 1 || newPage > totalPages) return;
    fetchLogs(newPage);
  };

  const formatAction = (action: string) => {
    return action.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
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
        <h1 className="text-2xl font-semibold text-fundinv-primary">Audit Logs</h1>
        <p className="text-sm text-fundinv-muted mt-1">Complete security and activity audit trail{totalLogs > 0 ? ` — ${totalLogs} entries` : ''}</p>
      </div>

      <Card>
        {loading ? (
          <div className="py-8 text-center text-sm text-fundinv-muted">Loading audit log...</div>
        ) : logs.length === 0 ? (
          <div className="py-8 text-center text-sm text-fundinv-muted">No audit entries yet.</div>
        ) : (
          <>
            <div className="overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-fundinv-border">
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">User</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Action</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Details</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">IP</th>
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr key={log.id} className="border-b border-fundinv-border last:border-0">
                      <td className="py-3 px-6">
                        <div className="text-fundinv-primary">{log.full_name || 'System'}</div>
                        <div className="text-xs text-fundinv-muted">{log.email || '—'}</div>
                      </td>
                      <td className="py-3 px-2">
                        <span className="px-2 py-1 text-xs font-medium bg-fundinv-surface rounded text-fundinv-primary">
                          {formatAction(log.action)}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted max-w-[250px] truncate">
                        {log.details || '—'}
                      </td>
                      <td className="py-3 px-2 text-xs text-fundinv-muted font-mono">
                        {log.ip_address || '—'}
                      </td>
                      <td className="py-3 px-6 text-xs text-fundinv-muted whitespace-nowrap">
                        {formatDate(log.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t border-fundinv-border">
                <p className="text-xs text-fundinv-muted">
                  Page {page} of {totalPages}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="secondary"
                    onClick={() => handlePageChange(page - 1)}
                    disabled={page <= 1}
                    className="px-3 py-1.5 text-xs"
                  >
                    Previous
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => handlePageChange(page + 1)}
                    disabled={page >= totalPages}
                    className="px-3 py-1.5 text-xs"
                  >
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
