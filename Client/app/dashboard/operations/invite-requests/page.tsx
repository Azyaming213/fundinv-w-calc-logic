'use client';

import { useState } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';

export default function InviteRequestsPage() {
  const [email, setEmail] = useState('');
  const [name, setName] = useState('');
  const [role, setRole] = useState('investor');
  const [message, setMessage] = useState<string | null>(null);
  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    try {
      await api.post('/api/auth/invite-requests', { email, full_name: name, role });
      setMessage('Invite request sent to an administrator for approval.');
      setEmail(''); setName('');
    } catch (err) {
      setMessage((err as { message?: string }).message || 'Invite request failed');
    }
  };
  return <div className="max-w-2xl mx-auto px-8 py-8"><div className="mb-8"><h1 className="text-2xl font-semibold text-fundinv-primary">Request an Invitation</h1><p className="text-sm text-fundinv-muted mt-1">Administrators approve and send all invitations.</p></div><Card><form onSubmit={submit} className="space-y-4"><Input label="Full Name" value={name} onChange={(event) => setName(event.target.value)} required /><Input label="Email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /><div><label className="text-sm font-medium text-fundinv-primary">Role</label><select value={role} onChange={(event) => setRole(event.target.value)} className="w-full mt-1 px-3 py-2 text-sm border border-fundinv-border rounded-md"><option value="investor">Investor</option><option value="manager">Manager</option><option value="operations">Operations</option></select></div>{message && <p className="text-sm text-fundinv-muted">{message}</p>}<Button type="submit">Submit Request</Button></form></Card></div>;
}
