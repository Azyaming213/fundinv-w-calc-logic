'use client';

import { useState } from 'react';
import Layout from '../components/Layout';
import Button from '../components/Button';
import Input from '../components/Input';
import Card from '../components/Card';
import { api } from '../lib/api';

export default function ForgotPasswordPage() {
    const [email, setEmail] = useState('');
    const [submitted, setSubmitted] = useState(false);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setError(null);
        setLoading(true);

        try {
            await api.post('/api/auth/forgot-password', { email });
            setSubmitted(true);
        } catch (err) {
            const message = (err as { message?: string }).message || 'Request failed';
            setError(message);
        } finally {
            setLoading(false);
        }
    };

    return (
        <Layout>
            <div className="min-h-[calc(100vh-200px)] flex items-center justify-center px-4">
                <div className="w-full max-w-md">
                    <Card>
                        {submitted ? (
                            <div className="text-center py-4">
                                <div className="w-14 h-14 bg-blue-50 rounded-full flex items-center justify-center mx-auto mb-4">
                                    <svg className="w-7 h-7 text-fundinv-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                                    </svg>
                                </div>
                                <h1 className="text-xl font-semibold text-fundinv-primary mb-2">Check your email</h1>
                                <p className="text-sm text-fundinv-muted mb-6">
                                    If an account exists with that email, we have sent a password reset link.
                                </p>
                                <a href="/login" className="text-sm text-fundinv-accent hover:underline">
                                    Return to sign in
                                </a>
                            </div>
                        ) : (
                            <>
                                <div className="text-center mb-6">
                                    <h1 className="text-2xl font-semibold text-fundinv-primary mb-2">Reset your password</h1>
                                    <p className="text-sm text-fundinv-muted">
                                        Enter your email and we will send you a reset link
                                    </p>
                                </div>

                                <form onSubmit={handleSubmit} className="flex flex-col gap-4">
                                    <Input
                                        label="Email address"
                                        type="email"
                                        placeholder="you@example.com"
                                        value={email}
                                        onChange={(e) => setEmail(e.target.value)}
                                        required
                                        disabled={loading}
                                        autoComplete="email"
                                    />

                                    {error && (
                                        <div className="px-3 py-2 bg-red-50 border border-red-200 rounded-md">
                                            <p className="text-sm text-red-700">{error}</p>
                                        </div>
                                    )}

                                    <Button type="submit" className="w-full mt-2" disabled={loading}>
                                        {loading ? 'Sending...' : 'Send reset link'}
                                    </Button>

                                    <div className="text-center">
                                        <a href="/login" className="text-xs text-fundinv-accent hover:underline">
                                            Back to sign in
                                        </a>
                                    </div>
                                </form>
                            </>
                        )}
                    </Card>
                </div>
            </div>
        </Layout>
    );
}
