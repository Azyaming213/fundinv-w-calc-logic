'use client';

import { useEffect, useState } from 'react';
import Card from '../../../components/Card';
import { api } from '../../../lib/api';

type Log = { id: number; full_name: string | null; email: string | null; action: string; details: string | null; created_at: string | null };

export default function OperationsAuditLogsPage() {
  const [logs, setLogs] = useState<Log[]>([]);
  useEffect(() => { api.get<{ logs: Log[] }>('/api/admin/audit-logs?page=1&page_size=100').then((data) => setLogs(data.logs || [])).catch(() => setLogs([])); }, []);
  return <div className="max-w-6xl mx-auto px-8 py-8"><div className="mb-8"><h1 className="text-2xl font-semibold text-fundinv-primary">Audit Logs</h1><p className="text-sm text-fundinv-muted mt-1">Operational activity and fund-flow history.</p></div><Card><div className="overflow-x-auto"><table className="w-full text-sm"><thead><tr className="border-b border-fundinv-border"><th className="text-left py-3">Time</th><th className="text-left py-3">User</th><th className="text-left py-3">Action</th><th className="text-left py-3">Details</th></tr></thead><tbody>{logs.map((log) => <tr key={log.id} className="border-b border-fundinv-border"><td className="py-3 text-xs text-fundinv-muted">{log.created_at ? new Date(log.created_at).toLocaleString() : '—'}</td><td className="py-3">{log.full_name || log.email || 'System'}</td><td className="py-3 font-mono text-xs">{log.action}</td><td className="py-3 text-xs text-fundinv-muted">{log.details || '—'}</td></tr>)}</tbody></table></div></Card></div>;
}
