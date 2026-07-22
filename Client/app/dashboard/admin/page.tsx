'use client';

import { useState, useEffect } from 'react';
import Card from '../../components/Card';
import Button from '../../components/Button';
import AuthGuard from '../../components/AuthGuard';
import { api } from '../../lib/api';
import { CLAIMS } from '../../lib/appconstants';
import type { AuditLogEntry } from '../../lib/types';

export default function AdminDashboard() {
  return (
    <AuthGuard allowedClaims={[CLAIMS.readAuditLogs]}>
      <AdminDashboardContent />
    </AuthGuard>
  );
}

function AdminDashboardContent() {
  const [totalUsers, setTotalUsers] = useState<number | null>(null);
  const [activeUsers, setActiveUsers] = useState<number | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(true);
  const [totalLogs, setTotalLogs] = useState(0);

  const fetchStats = async () => {
    setStatsLoading(true);
    try {
      const data = await api.get<{ total_users: number; active_users: number }>('/api/admin/stats');
      setTotalUsers(data.total_users);
      setActiveUsers(data.active_users);
    } catch {
      // Stats will stay as null (shows — —)
    } finally {
      setStatsLoading(false);
    }
  };

  const fetchLogs = async (pageNum: number) => {
    setLogsLoading(true);
    try {
      const data = await api.get<{ logs: AuditLogEntry[]; total: number; page: number; page_size: number; total_pages: number }>(`/api/admin/audit-logs?page=${pageNum}&page_size=5`);
      setLogs(data.logs);
      setTotalLogs(data.total);
    } catch {
      setLogs([]);
    } finally {
      setLogsLoading(false);
    }
  };

  useEffect(() => {
    fetchStats();
    fetchLogs(1);
  }, []);

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
        <h1 className="text-2xl font-semibold text-fundinv-primary">Admin Console</h1>
        <p className="text-sm text-fundinv-muted mt-1">Platform oversight and audit trail</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
        <Card title="Total Users">
          <p className="text-2xl font-semibold text-fundinv-primary">
            {statsLoading ? '— —' : totalUsers}
          </p>
        </Card>

        <Card title="Active Users">
          <p className="text-2xl font-semibold text-fundinv-primary">
            {statsLoading ? '— —' : activeUsers}
          </p>
        </Card>
      </div>

      <Card title={`Recent Activity${totalLogs > 0 ? ` (${totalLogs} entries)` : ''}`}>
        {logsLoading ? (
          <div className="py-8 text-center text-sm text-fundinv-muted">Loading activity...</div>
        ) : logs.length === 0 ? (
          <div className="py-8 text-center text-sm text-fundinv-muted">No activity yet.</div>
        ) : (
          <>
            <div className="overflow-x-auto -mx-6">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-fundinv-border">
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">User</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Action</th>
                    <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Details</th>
                    <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.slice(0, 5).map((log) => (
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
                      <td className="py-3 px-2 text-xs text-fundinv-muted max-w-[200px] truncate">
                        {log.details || '—'}
                      </td>
                      <td className="py-3 px-6 text-xs text-fundinv-muted whitespace-nowrap">
                        {formatDate(log.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex items-center justify-between mt-4 pt-4 border-t border-fundinv-border">
              <p className="text-xs text-fundinv-muted">
                Showing 5 of {totalLogs} entries
              </p>
              <a href="/dashboard/admin/audit-logs" className="text-sm text-fundinv-accent hover:underline">
                View Full Audit Logs →
              </a>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
