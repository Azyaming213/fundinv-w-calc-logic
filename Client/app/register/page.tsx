'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Layout from '../components/Layout';
import Button from '../components/Button';
import Input from '../components/Input';
import Card from '../components/Card';
import { api } from '../lib/api';

function RegisterForm() {
    const router = useRouter();
    const searchParams = useSearchParams();

    const [token, setToken] = useState('');
    const [password, setPassword] = useState('');
    const [confirmPassword, setConfirmPassword] = useState('');
    const [error, setError] = useState<string | null>(null);
    const [success, setSuccess] = useState(false);
    const [loading, setLoading] = useState(false);

    useEffect(() => {
        const urlToken = searchParams.get('token');
        if (urlToken) {
            setToken(urlToken);
        }
    }, [searchParams]);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);

        if (!token) {
            setError('No invitation token provided. Please use the link from your invitation.');
            return;
        }

        if (password.length < 8) {
            setError('Password must be at least 8 characters.');
            return;
        }

        if (password !== confirmPassword) {
            setError('Passwords do not match.');
            return;
        }

        setLoading(true);

        try {
            await api.post('/api/auth/register', { token, password });
            setSuccess(true);
            setTimeout(() => router.push('/login'), 2500);
        } catch (err) {
            const message = (err as { message?: string }).message || 'Registration failed';
            setError(message);
        } finally {
            setLoading(false);
        }
    };

    if (success) {
        return (
            <div className="w-full max-w-md">
                <Card>
                    <div className="text-center py-4">
                        <div className="w-14 h-14 bg-emerald-50 rounded-full flex items-center justify-center mx-auto mb-4">
                            <svg className="w-7 h-7 text-fundinv-success" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                            </svg>
                        </div>
                        <h1 className="text-xl font-semibold text-fundinv-primary mb-2">Account created</h1>
                        <p className="text-sm text-fundinv-muted">
                            Your account is ready. Redirecting you to sign in...
                        </p>
                    </div>
                </Card>
            </div>
        );
    }

    return (
        <div className="w-full max-w-md">
            <Card>
                <div className="text-center mb-6">
                    <h1 className="text-2xl font-semibold text-fundinv-primary mb-2">Complete your registration</h1>
                    <p className="text-sm text-fundinv-muted">Set a password to activate your account</p>
                </div>

                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                    {!searchParams.get('token') && (
                        <Input
                            label="Invitation token"
                            type="text"
                            placeholder="Paste your invitation token"
                            value={token}
                            onChange={(e) => setToken(e.target.value)}
                            required
                            disabled={loading}
                        />
                    )}

                    <Input
                        label="Password"
                        type="password"
                        placeholder="At least 8 characters"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        required
                        disabled={loading}
                        autoComplete="new-password"
                    />

                    <Input
                        label="Confirm password"
                        type="password"
                        placeholder="Re-enter your password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        required
                        disabled={loading}
                        autoComplete="new-password"
                    />

                    {error && (
                        <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                            <p className="text-sm text-red-700">{error}</p>
                        </div>
                    )}

                    <Button type="submit" className="w-full mt-2" disabled={loading}>
                        {loading ? 'Creating account...' : 'Create account'}
                    </Button>

                    <div className="text-center">
                        <a href="/login" className="text-xs text-fundinv-accent hover:underline">
                            Already have an account? Sign in
                        </a>
                    </div>
                </form>
            </Card>
        </div>
    );
}

export default function RegisterPage() {
    return (
        <Layout>
            <div className="min-h-[calc(100vh-200px)] flex items-center justify-center px-4">
                <Suspense fallback={<div className="text-sm text-fundinv-muted">Loading...</div>}>
                    <RegisterForm />
                </Suspense>
            </div>
        </Layout>
    );
}
