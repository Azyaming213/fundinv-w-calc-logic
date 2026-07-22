'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Layout from '../components/Layout';
import Button from '../components/Button';
import Input from '../components/Input';
import Card from '../components/Card';
import { api } from '../lib/api';
import { setToken, getDashboardPath, User } from '../lib/auth';
import type { LoginResponse } from '../lib/types';

function LoginForm() {
    const router = useRouter();
    const searchParams = useSearchParams();
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [loading, setLoading] = useState(false);
    const [expired, setExpired] = useState(false);

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

            setToken(data.access_token);
            router.push(getDashboardPath(data.user.role as User['role']));
        } catch (err) {
            const message = (err as { message?: string }).message || 'Login failed';
            setError(message);
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

                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
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

                    {error && (
                        <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                            <p className="text-sm text-red-700">{error}</p>
                        </div>
                    )}

                    <Button type="submit" className="w-full mt-2" disabled={loading}>
                        {loading ? 'Signing in...' : 'Sign in'}
                    </Button>

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
