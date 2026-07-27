'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Layout from '../components/Layout';
import Button from '../components/Button';
import Input from '../components/Input';
import Card from '../components/Card';
import { api } from '../lib/api';
import { setSessionUser, getDashboardPath, User } from '../lib/auth';
import type { LoginResponse } from '../lib/types';

function LoginForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [expired, setExpired] = useState(false);
    const [mfaToken, setMfaToken] = useState<string | null>(null);
    const [mfaCode, setMfaCode] = useState('');

    useEffect(() => {
        if (searchParams.get('expired') === 'true') {
            setExpired(true);
        }
    }, [searchParams]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setExpired(false);
        setLoading(true);

        try {
            const data = await api.post<LoginResponse>('/api/auth/login', {
                email,
                password,
            });

            if (data.mfa_required && data.mfa_token) {
                setMfaToken(data.mfa_token);
                return;
            }
            if (!data.user) throw new Error('Login response did not include a user');
            setSessionUser({
                id: data.user.user_id,
                email: data.user.email,
                full_name: data.user.full_name,
                role: data.user.role as User['role'],
                is_active: data.user.is_active,
                claims: data.user.claims || [],
            });
            router.push(getDashboardPath(data.user.role as User['role']));
        } catch (err) {
            const message = (err as { message?: string }).message || 'Login failed';
            setError(message);
        } finally {
            setLoading(false);
        }
    };

    const handleMfaSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        if (!mfaToken) return;
        setError(null);
        setLoading(true);
        try {
            const data = await api.post<LoginResponse>('/api/auth/mfa/login', {
                mfa_token: mfaToken,
                code: mfaCode,
            });
            if (!data.user) throw new Error('MFA login response did not include a user');
            setSessionUser({
                id: data.user.user_id,
                email: data.user.email,
                full_name: data.user.full_name,
                role: data.user.role as User['role'],
                is_active: data.user.is_active,
                claims: data.user.claims || [],
            });
            router.push(getDashboardPath(data.user.role as User['role']));
        } catch (err) {
            setError((err as { message?: string }).message || 'MFA verification failed');
        } finally {
            setLoading(false);
        }
    };

    return (
        <div className="w-full max-w-md">
            <Card>
                <div className="text-center mb-6">
                    <h1 className="text-2xl font-semibold text-fundinv-primary mb-2">Welcome back</h1>
                    <p className="text-sm text-fundinv-muted">Sign in to access your portfolio</p>
                </div>

                {expired && (
                    <div className="px-3 py-2 bg-amber-50 border border-amber-200 rounded-md mb-4">
                        <p className="text-sm text-amber-800">Your session has expired. Please sign in again.</p>
                    </div>
                )}

                <form onSubmit={mfaToken ? handleMfaSubmit : handleSubmit} className="flex flex-col gap-4">
                    {mfaToken ? (
                      <>
                        <p className="text-sm text-fundinv-muted">Enter the six-digit code from your authenticator app.</p>
                        <Input
                          label="Authentication code"
                          inputMode="numeric"
                          pattern="[0-9]{6}"
                          maxLength={6}
                          value={mfaCode}
                          onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                          required
                          disabled={loading}
                          autoComplete="one-time-code"
                        />
                      </>
                    ) : (
                      <>
                    <Input
                        label="Email address"
                        type="email"
                        placeholder="investor@example.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        disabled={loading}
                        autoComplete="email"
                    />
                    <Input
                        label="Password"
                        type="password"
                        placeholder="Enter your password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        disabled={loading}
                        autoComplete="current-password"
                    />
                      </>
                    )}

                    {error && (
                        <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                            <p className="text-sm text-red-700">{error}</p>
                        </div>
                    )}

                    <Button type="submit" className="w-full mt-2" disabled={loading}>
                        {loading ? 'Verifying...' : mfaToken ? 'Verify and sign in' : 'Sign in'}
                    </Button>

                    {mfaToken && (
                      <button type="button" onClick={() => { setMfaToken(null); setMfaCode(''); setError(null); }} className="text-xs text-fundinv-accent hover:underline">
                        Use a different account
                      </button>
                    )}

                    <div className="text-center">
                        <a href="/forgot-password" className="text-xs text-fundinv-accent hover:underline">
                            Forgot your password?
                        </a>
                    </div>
                </form>
            </Card>

            <p className="text-center text-xs text-fundinv-muted mt-6">
                Access is by invitation only. Contact your fund manager for access.
            </p>
        </div>
    );
}

export default function LoginPage() {
    return (
        <Layout>
            <div className="min-h-[calc(100vh-200px)] flex items-center justify-center px-4">
                <Suspense fallback={<div className="text-sm text-fundinv-muted">Loading...</div>}>
                    <LoginForm />
                </Suspense>
            </div>
        </Layout>
    );
}
