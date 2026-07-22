'use client';

import { useState, useEffect } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import { api } from '../../../lib/api';
import type { InvestorRow, ManagerOption } from '../../../lib/types';

export default function AdminInvestorsPage() {
  const [investors, setInvestors] = useState<InvestorRow[]>([]);
  const [managers, setManagers] = useState<ManagerOption[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [assigningId, setAssigningId] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<{ investors: InvestorRow[]; managers: ManagerOption[] }>('/api/admin/investors');
      setInvestors(data.investors || []);
      setManagers(data.managers || []);
    } catch (err) {
      setError((err as { message?: string }).message || 'Failed to load investors');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchData(); }, []);

  const assignManager = async (investorId: number, managerId: number | null) => {
    setAssigningId(investorId);
    try {
      await api.put(`/api/admin/investors/${investorId}?manager_id=${managerId ?? 0}`);
      const inv = investors.find(i => i.id === investorId);
      const mgr = managers.find(m => m.id === managerId);
      setToast(`${inv?.full_name} ${managerId ? 'assigned to' : 'unassigned from'} ${mgr?.full_name || 'any manager'}`);
      setTimeout(() => setToast(null), 3000);
      await fetchData();
    } catch (err) {
      setToast('Assignment failed: ' + ((err as any)?.message || 'Error'));
      setTimeout(() => setToast(null), 4000);
    } finally {
      setAssigningId(null);
    }
  };

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto px-8 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-fundinv-border rounded" />
          <div className="h-96 bg-fundinv-border rounded" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-fundinv-primary">Investor Management</h1>
        <p className="text-sm text-fundinv-muted mt-1">Assign investors to fund managers</p>
      </div>

      {toast && (
        <div className="mb-4 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-md text-sm text-emerald-700">{toast}</div>
      )}

      {error ? (
        <Card><div className="py-8 text-center"><p className="text-sm text-fundinv-danger mb-3">{error}</p><Button variant="secondary" onClick={fetchData}>Retry</Button></div></Card>
      ) : (
        <Card>
          <div className="overflow-x-auto -mx-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-fundinv-border">
                  <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Name</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Email</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Status</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Current Manager</th>
                  <th className="text-right py-3 px-6 font-medium text-fundinv-muted">Assign</th>
                </tr>
              </thead>
              <tbody>
                {investors.map((inv) => (
                  <tr key={inv.id} className="border-b border-fundinv-border last:border-0 hover:bg-fundinv-surface/50">
                    <td className="py-3 px-6 font-medium text-fundinv-primary">{inv.full_name}</td>
                    <td className="py-3 px-2 text-fundinv-muted text-xs">{inv.email}</td>
                    <td className="py-3 px-2">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${inv.is_active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'}`}>
                        {inv.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="py-3 px-2">
                      {inv.manager_name ? (
                        <div>
                          <p className="font-medium text-fundinv-primary text-xs">{inv.manager_name}</p>
                          <p className="text-[10px] text-fundinv-muted">{inv.manager_email}</p>
                        </div>
                      ) : (
                        <span className="text-xs text-fundinv-muted">Unassigned</span>
                      )}
                    </td>
                    <td className="py-3 px-6 text-right">
                      <select
                        value={inv.manager_id ?? 0}
                        onChange={(e) => assignManager(inv.id, Number(e.target.value) || null)}
                        disabled={assigningId === inv.id}
                        className="px-2 py-1 text-xs border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                      >
                        <option value={0}>Unassigned</option>
                        {managers.map((m) => (
                          <option key={m.id} value={m.id}>{m.full_name}</option>
                        ))}
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
