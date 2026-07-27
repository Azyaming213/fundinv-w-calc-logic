'use client';

import { useState, useEffect, useCallback } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import InviteModal from '../../../components/InviteModal';
import { api } from '../../../lib/api';
import type { Invite } from '../../../lib/types';

export default function AppSettingsPage() {
  const [showInviteModal, setShowInviteModal] = useState(false);
  const [invites, setInvites] = useState<Invite[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<number | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  type InviteRequestRow = { id: number; email: string; full_name: string; role: string; status: string; requested_by: string | null };
  const [inviteRequests, setInviteRequests] = useState<InviteRequestRow[]>([]);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  const fetchInvites = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<{ invites: Invite[] }>('/api/auth/invites');
      setInvites(data.invites || []);
      const requestData = await api.get<{ requests: InviteRequestRow[] }>('/api/admin/invite-requests');
      setInviteRequests(requestData.requests || []);
    } catch (err) {
      const message = (err as { message?: string }).message || 'Failed to load invites';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  const reviewInviteRequest = async (requestId: number, decision: 'approve' | 'reject') => {
    const notes = decision === 'reject' ? prompt('Reason for rejection') || 'Rejected by administrator' : undefined;
    try {
      await api.post(`/api/admin/invite-requests/${requestId}/review`, { decision, notes });
      showToast(decision === 'approve' ? 'Invitation approved and emailed' : 'Invite request rejected');
      fetchInvites();
    } catch (err) {
      showToast((err as { message?: string }).message || 'Invite review failed');
    }
  };

  useEffect(() => {
    fetchInvites();
  }, [fetchInvites]);

  const handleInviteCreated = () => {
    setShowInviteModal(false);
    fetchInvites();
  };

  const handleDelete = async (invite: Invite) => {
    if (!confirm(`Delete invite for ${invite.email}?`)) return;
    setActionLoading(invite.id);
    try {
      await api.delete(`/api/auth/invites/${invite.id}`);
      showToast(`Invite for ${invite.email} deleted`);
      fetchInvites();
    } catch (err) {
      showToast(`Delete failed: ${(err as { message?: string }).message || 'Error'}`);
    } finally {
      setActionLoading(null);
    }
  };

  const handleResend = async (invite: Invite) => {
    setActionLoading(invite.id);
    try {
      await api.post(`/api/auth/invites/${invite.id}/resend`);
      showToast(`Invite resent to ${invite.email}`);
      fetchInvites();
    } catch (err) {
      showToast(`Resend failed: ${(err as { message?: string }).message || 'Error'}`);
    } finally {
      setActionLoading(null);
    }
  };

  const getStatus = (invite: Invite) => {
    if (invite.used) return { label: 'Accepted', color: 'text-fundinv-success bg-emerald-50' };
    if (new Date(invite.expires_at) < new Date()) return { label: 'Expired', color: 'text-fundinv-danger bg-red-50' };
    return { label: 'Pending', color: 'text-fundinv-warning bg-amber-50' };
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  };

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-fundinv-primary">App Settings</h1>
        <p className="text-sm text-fundinv-muted mt-1">Manage user invitations and platform settings</p>
      </div>

      {toast && (
        <div className="mb-4 px-4 py-2.5 bg-emerald-50 border border-emerald-200 rounded-md text-sm text-emerald-700">{toast}</div>
      )}

      <Card title="Invite User" className="mb-6">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-fundinv-muted">
              Send an invitation to a new investor or operations user. They will receive a link to set their password.
            </p>
          </div>
          <Button onClick={() => setShowInviteModal(true)}>Invite User</Button>
        </div>
      </Card>

      <Card title="Pending Invites">
        {loading ? (
          <div className="py-8 text-center text-sm text-fundinv-muted">Loading invites...</div>
        ) : error ? (
          <div className="py-8 text-center">
            <p className="text-sm text-fundinv-danger mb-3">{error}</p>
            <Button variant="secondary" onClick={fetchInvites}>Retry</Button>
          </div>
        ) : invites.length === 0 ? (
          <div className="py-8 text-center text-sm text-fundinv-muted">
            No invites yet. Click &quot;Invite User&quot; to get started.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-fundinv-border">
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Name</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Email</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Role</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Status</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Created</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Expires</th>
                  <th className="text-right py-3 px-2 font-medium text-fundinv-muted">Actions</th>
                </tr>
              </thead>
              <tbody>
                {invites.map((invite) => {
                  const status = getStatus(invite);
                  const isBusy = actionLoading === invite.id;
                  return (
                    <tr key={invite.id} className="border-b border-fundinv-border last:border-0">
                      <td className="py-3 px-2 text-fundinv-primary">{invite.full_name}</td>
                      <td className="py-3 px-2 text-fundinv-muted">{invite.email}</td>
                      <td className="py-3 px-2">
                        <span className="px-2 py-1 text-xs font-medium bg-fundinv-surface rounded text-fundinv-primary capitalize">
                          {invite.role}
                        </span>
                      </td>
                      <td className="py-3 px-2">
                        <span className={`px-2 py-1 text-xs font-medium rounded ${status.color}`}>
                          {status.label}
                        </span>
                      </td>
                      <td className="py-3 px-2 text-fundinv-muted">{formatDate(invite.created_at)}</td>
                      <td className="py-3 px-2 text-fundinv-muted">{formatDate(invite.expires_at)}</td>
                      <td className="py-3 px-2 text-right">
                        <div className="flex gap-1 justify-end">
                          {!invite.used && (
                            <Button variant="secondary" onClick={() => handleResend(invite)} disabled={isBusy} className="text-xs py-1 px-2">
                              {isBusy ? '...' : 'Resend'}
                            </Button>
                          )}
                          <Button variant="secondary" onClick={() => handleDelete(invite)} disabled={isBusy} className="text-xs py-1 px-2 !text-red-600 !border-red-200 hover:!bg-red-50">
                            {isBusy ? '...' : 'Delete'}
                          </Button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card title="Operations Invite Requests" className="mt-6">
        {inviteRequests.length === 0 ? <p className="py-6 text-sm text-fundinv-muted">No pending operations requests.</p> : <div className="space-y-3">{inviteRequests.filter((request) => request.status === 'pending_admin_review').map((request) => <div key={request.id} className="flex items-center justify-between gap-4 border-b border-fundinv-border pb-3"><div><p className="text-sm font-medium text-fundinv-primary">{request.full_name} · {request.email}</p><p className="text-xs text-fundinv-muted">{request.role} requested by {request.requested_by || 'operations'}</p></div><div className="flex gap-2"><Button onClick={() => reviewInviteRequest(request.id, 'approve')} className="text-xs py-1 px-2">Approve</Button><Button variant="secondary" onClick={() => reviewInviteRequest(request.id, 'reject')} className="text-xs py-1 px-2 text-red-600">Reject</Button></div></div>)}</div>}
      </Card>

      {showInviteModal && (
        <InviteModal onClose={handleInviteCreated} />
      )}
    </div>
  );
}
