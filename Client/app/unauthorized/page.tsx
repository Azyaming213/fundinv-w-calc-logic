'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import Layout from '../components/Layout';
import Card from '../components/Card';
import Button from '../components/Button';
import { getUser, getDashboardPath } from '../lib/auth';

export default function UnauthorizedPage() {
    const router = useRouter();
    const [countdown, setCountdown] = useState(5);
    const [dashboardPath, setDashboardPath] = useState('/');

    useEffect(() => {
        const user = getUser();
        const path = user ? getDashboardPath(user.role) : '/login';
        setDashboardPath(path);
    }, []);

    useEffect(() => {
        const timer = setInterval(() => {
            setCountdown((prev) => (prev <= 1 ? 0 : prev - 1));
        }, 1000);
        return () => clearInterval(timer);
    }, []);

    useEffect(() => {
        if (countdown === 0 && dashboardPath) {
            router.replace(dashboardPath);
        }
    }, [countdown, dashboardPath, router]);

    return (
        <Layout>
            <div className="min-h-[calc(100vh-200px)] flex items-center justify-center px-4">
                <div className="w-full max-w-md">
                    <Card>
                        <div className="text-center py-4">
                            <div className="w-14 h-14 bg-red-50 rounded-full flex items-center justify-center mx-auto mb-4">
                                <svg className="w-7 h-7 text-fundinv-danger" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                                </svg>
                            </div>

                            <h1 className="text-xl font-semibold text-fundinv-primary mb-2">Access denied</h1>
                            <p className="text-sm text-fundinv-muted mb-1">
                                You do not have permission to view that page.
                            </p>
                            <p className="text-sm text-fundinv-muted mb-6">
                                Redirecting you to your dashboard in {countdown}s...
                            </p>

                            <Button onClick={() => router.replace(dashboardPath)} className="w-full">
                                Go to my dashboard now
                            </Button>
                        </div>
                    </Card>
                </div>
            </div>
        </Layout>
    );
}
