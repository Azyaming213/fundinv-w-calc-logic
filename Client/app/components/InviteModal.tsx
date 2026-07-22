'use client';

import { useState } from 'react';
import Button from './Button';
import Input from './Input';
import { api } from '../lib/api';
import { ROLES } from '../lib/appconstants';
import type { InviteResponse } from '../lib/types';

interface InviteModalProps {
    onClose: () => void;
}

export default function InviteModal({ onClose }: InviteModalProps) {
    const [email, setEmail] = useState('');
    const [fullName, setFullName] = useState('');
    const [role, setRole] = useState(ROLES.INVESTOR);
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState<InviteResponse | null>(null);
    const [copied, setCopied] = useState(false);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);

        try {
            const data = await api.post<InviteResponse>('/api/auth/invites', {
                email,
                full_name: fullName,
                role,
            });
            setResult(data);
        } catch (err) {
            const message = (err as { message?: string }).message || 'Failed to create invite';
            setError(message);
        } finally {
            setLoading(false);
        }
    };

    const inviteLink = result
        ? `${window.location.origin}/register?token=${result.token}`
        : '';

    const handleCopy = async () => {
        await navigator.clipboard.writeText(inviteLink);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
    };

    return (
        <div className="fixed inset-0 z-50 flex items-center justify-center px-4">
            <div className="fixed inset-0 bg-black/40" onClick={onClose} />

            <div className="relative w-full max-w-md bg-white rounded-lg shadow-xl border border-fundinv-border">
                <div className="px-6 py-4 border-b border-fundinv-border flex items-center justify-between">
                    <h2 className="text-lg font-semibold text-fundinv-primary">Invite Investor</h2>
                    <button
                        onClick={onClose}
                        className="text-fundinv-muted hover:text-fundinv-primary transition"
                        aria-label="Close"
                    >
                        <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                    </button>
                </div>

                <div className="px-6 py-5">
                    {result ? (
                        <div>
                            <div className="flex items-center gap-2 mb-4">
                                <div className="w-8 h-8 bg-emerald-50 rounded-full flex items-center justify-center">
                                    <svg className="w-4 h-4 text-fundinv-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                    </svg>
                                </div>
                                <p className="text-sm font-medium text-fundinv-primary">Invitation created</p>
                            </div>

                            <p className="text-sm text-fundinv-muted mb-3">
                                Share this link with {result.email}. It expires in 7 days.
                            </p>

                            <div className="flex gap-2 mb-4">
                                <input
                                    readOnly
                                    value={inviteLink}
                                    className="flex-1 px-3 py-2 text-xs bg-fundinv-surface border border-fundinv-border rounded-md text-fundinv-primary"
                                />
                                <Button variant="secondary" onClick={handleCopy}>
                                    {copied ? 'Copied' : 'Copy'}
                                </Button>
                            </div>

                            <Button className="w-full" onClick={onClose}>
                                Done
                            </Button>
                        </div>
                    ) : (
                        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                            <Input
                                label="Full name"
                                type="text"
                                placeholder="Jane Investor"
                                value={fullName}
                                onChange={(e) => setFullName(e.target.value)}
                                required
                                disabled={loading}
                            />

                            <Input
                                label="Email address"
                                type="email"
                                placeholder="jane@example.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                                disabled={loading}
                            />

                            <div className="flex flex-col gap-1.5">
                                <label className="text-sm font-medium text-fundinv-primary">Role</label>
                                <select
                                    value={role}
                                    onChange={(e) => setRole(e.target.value)}
                                    disabled={loading}
                                    className="px-3 py-2 text-sm border border-fundinv-border rounded-md text-fundinv-primary bg-white focus:outline-none focus:ring-2 focus:ring-fundinv-accent"
                                >
                                    <option value={ROLES.INVESTOR}>Investor</option>
                                    <option value={ROLES.OPERATIONS}>Operations</option>
                                    <option value={ROLES.MANAGER}>Manager</option>
                                </select>
                            </div>

                            {error && (
                                <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                                    <p className="text-sm text-red-700">{error}</p>
                                </div>
                            )}

                            <Button type="submit" className="w-full mt-1" disabled={loading}>
                                {loading ? 'Creating invite...' : 'Create invitation'}
                            </Button>
                        </form>
                    )}
                </div>
            </div>
        </div>
    );
}
