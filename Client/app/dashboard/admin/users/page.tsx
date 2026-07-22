'use client';

import { useState, useEffect } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';
import type { UserRecord, Role } from '../../../lib/types';

export default function AdminUsersPage() {
  const [users, setUsers] = useState<UserRecord[]>([]);
  const [roles, setRoles] = useState<Role[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [editingUser, setEditingUser] = useState<UserRecord | null>(null);
  const [editEmail, setEditEmail] = useState('');
  const [editName, setEditName] = useState('');
  const [editRoleId, setEditRoleId] = useState<number>(0);
  const [editPassword, setEditPassword] = useState('');
  const [editActive, setEditActive] = useState(true);
  const [saving, setSaving] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);
  const [editSuccess, setEditSuccess] = useState<string | null>(null);

  const fetchUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.get<{ users: UserRecord[]; roles: Role[] }>('/api/admin/users');
      setUsers(data.users || []);
      setRoles(data.roles || []);
    } catch (err) {
      setError((err as { message?: string }).message || 'Failed to load users');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchUsers();
  }, []);

  const openEdit = (user: UserRecord) => {
    setEditingUser(user);
    setEditEmail(user.email);
    setEditName(user.full_name);
    setEditRoleId(user.role_id);
    setEditPassword('');
    setEditActive(user.is_active);
    setEditError(null);
    setEditSuccess(null);
  };

  const closeEdit = () => {
    setEditingUser(null);
    setEditError(null);
    setEditSuccess(null);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingUser) return;
    setSaving(true);
    setEditError(null);
    setEditSuccess(null);
    try {
      const body: Record<string, string | number | boolean> = {};
      if (editEmail !== editingUser.email) body.email = editEmail;
      if (editName !== editingUser.full_name) body.full_name = editName;
      if (editRoleId !== editingUser.role_id) body.role_id = editRoleId;
      if (editPassword) body.new_password = editPassword;
      if (editActive !== editingUser.is_active) body.is_active = editActive;

      await api.put(`/api/admin/users/${editingUser.id}`, body);
      setEditSuccess('User updated successfully');
      await fetchUsers();
      setTimeout(() => closeEdit(), 1000);
    } catch (err) {
      setEditError((err as { message?: string }).message || 'Failed to update user');
    } finally {
      setSaving(false);
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
        <h1 className="text-2xl font-semibold text-fundinv-primary">User Management</h1>
        <p className="text-sm text-fundinv-muted mt-1">{users.length} user{users.length !== 1 ? 's' : ''} registered</p>
      </div>

      {error ? (
        <Card>
          <div className="py-8 text-center">
            <p className="text-sm text-fundinv-danger mb-3">{error}</p>
            <Button variant="secondary" onClick={fetchUsers}>Retry</Button>
          </div>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto -mx-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-fundinv-border">
                  <th className="text-left py-3 px-6 font-medium text-fundinv-muted">Name</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Email</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Role</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Status</th>
                  <th className="text-left py-3 px-2 font-medium text-fundinv-muted">Last Login</th>
                  <th className="text-right py-3 px-6 font-medium text-fundinv-muted">Actions</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.id} className="border-b border-fundinv-border last:border-0 hover:bg-fundinv-surface/50">
                    <td className="py-3 px-6 font-medium text-fundinv-primary">{user.full_name}</td>
                    <td className="py-3 px-2 text-fundinv-muted">{user.email}</td>
                    <td className="py-3 px-2">
                      <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-fundinv-surface capitalize">
                        {user.role}
                      </span>
                    </td>
                    <td className="py-3 px-2">
                      <span className={`px-2 py-0.5 text-xs font-medium rounded-full ${
                        user.is_active ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700'
                      }`}>
                        {user.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </td>
                    <td className="py-3 px-2 text-fundinv-muted text-xs">
                      {user.last_login_at ? new Date(user.last_login_at).toLocaleDateString() : 'Never'}
                    </td>
                    <td className="py-3 px-6 text-right">
                      <Button variant="secondary" onClick={() => openEdit(user)} className="text-xs py-1 px-3">
                        Edit
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {editingUser && (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
          <div className="fixed inset-0 bg-black/40" onClick={closeEdit} />
          <div className="relative w-full max-w-md bg-white rounded-lg shadow-xl border border-fundinv-border">
            <div className="px-6 py-4 border-b border-fundinv-border flex items-center justify-between">
              <h2 className="text-lg font-semibold text-fundinv-primary">Edit User</h2>
              <button onClick={closeEdit} className="text-fundinv-muted hover:text-fundinv-primary transition" aria-label="Close">
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="px-6 py-5">
              {editSuccess ? (
                <div className="text-center py-4">
                  <div className="w-12 h-12 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-3">
                    <svg className="w-6 h-6 text-fundinv-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                  </div>
                  <p className="text-sm font-medium text-fundinv-primary">{editSuccess}</p>
                </div>
              ) : (
                <form onSubmit={handleSave} className="flex flex-col gap-4">
                  <Input
                    label="Full Name"
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    required
                    disabled={saving}
                  />
                  <Input
                    label="Email"
                    type="email"
                    value={editEmail}
                    onChange={(e) => setEditEmail(e.target.value)}
                    required
                    disabled={saving}
                  />
                  <div className="flex flex-col gap-1.5">
                    <label className="text-sm font-medium text-fundinv-primary">Role</label>
                    <select
                      value={editRoleId}
                      onChange={(e) => setEditRoleId(Number(e.target.value))}
                      disabled={saving}
                      className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                    >
                      {roles.map((r) => (
                        <option key={r.id} value={r.id}>{r.name}</option>
                      ))}
                    </select>
                  </div>
                  <Input
                    label="New Password (leave blank to keep current)"
                    type="password"
                    placeholder="New password"
                    value={editPassword}
                    onChange={(e) => setEditPassword(e.target.value)}
                    disabled={saving}
                  />
                  <label className="flex items-center gap-3 cursor-pointer">
                    <input
                      type="checkbox"
                      checked={editActive}
                      onChange={(e) => setEditActive(e.target.checked)}
                      disabled={saving}
                      className="w-4 h-4 text-fundinv-accent border-fundinv-border rounded focus:ring-fundinv-accent"
                    />
                    <span className="text-sm text-fundinv-primary">Active account</span>
                  </label>

                  {editError && (
                    <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                      <p className="text-sm text-red-700">{editError}</p>
                    </div>
                  )}

                  <div className="flex gap-2 mt-1">
                    <Button type="button" variant="secondary" onClick={closeEdit} disabled={saving} className="flex-1">Cancel</Button>
                    <Button type="submit" disabled={saving} className="flex-1">
                      {saving ? 'Saving...' : 'Save Changes'}
                    </Button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
