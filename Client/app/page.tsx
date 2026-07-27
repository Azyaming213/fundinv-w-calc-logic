'use client';

import Layout from './components/Layout';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { getUser, getDashboardPath } from './lib/auth';

export default function Home() {
    const router = useRouter();
    const [checking, setChecking] = useState(true);

    useEffect(() => {
        const user = getUser();
        if (user) {
            const dash = getDashboardPath(user.role);
            router.replace(dash);
            return;
        }
        setChecking(false);
    }, [router]);

    const handleAccessPortfolio = () => {
        router.push('/login');
    };

    const handleRegister = () => {
        router.push('/register');
    };

    if (checking) {
        return (
            <div className="min-h-screen flex items-center justify-center bg-fundinv-surface">
                <div className="text-sm text-fundinv-muted">Redirecting…</div>
            </div>
        );
    }

    return (
        <Layout>
            <section className="max-w-5xl mx-auto px-6 sm:px-8 pt-24 pb-16 text-center">
                <div className="inline-flex items-center gap-2 px-3 py-1 bg-white border border-fundinv-border text-fundinv-primary text-xs rounded-full mb-6 shadow-sm">
                    <span className="w-1.5 h-1.5 rounded-full bg-fundinv-success" />
                    By invitation only · Regulated fund management
                </div>

                <h1 className="text-4xl sm:text-5xl md:text-6xl font-semibold text-fundinv-primary mb-5 tracking-tight leading-tight">
                    Your portfolio,
                    <br />
                    <span className="text-fundinv-muted">clear and secure.</span>
                </h1>

                <p className="text-base sm:text-lg text-fundinv-muted max-w-2xl mx-auto mb-10 leading-relaxed">
                    Track fund performance, manage capital movements, and access investment data through a secure investor portal.
                </p>

                <div className="flex flex-col sm:flex-row gap-3 justify-center items-center">
                    <button
                        onClick={handleAccessPortfolio}
                        className="px-6 py-3 text-sm font-medium bg-fundinv-primary text-white rounded-md hover:bg-fundinv-primary-hover transition shadow-sm w-full sm:w-auto"
                    >
                        Access your portfolio
                    </button>

                    <button
                        onClick={handleRegister}
                        className="px-6 py-3 text-sm font-medium border border-fundinv-border bg-white text-fundinv-primary rounded-md hover:bg-slate-50 transition w-full sm:w-auto"
                    >
                        Register with invite
                    </button>
                </div>

                <p className="mt-4 text-xs text-fundinv-muted">
                    Registration requires a valid invitation token.
                </p>
            </section>

            <section className="max-w-5xl mx-auto px-6 sm:px-8 pb-20">
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <FeatureCard
                        iconBg="bg-blue-50"
                        iconColor="text-fundinv-accent"
                        title="Bank-grade security"
                        description="Multi-factor authentication and role-based access control protect every account."
                        icon={
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 12l2 2 4-4M7.835 4.697a3.42 3.42 0 001.946-.806 3.42 3.42 0 014.438 0 3.42 3.42 0 001.946.806 3.42 3.42 0 013.138 3.138 3.42 3.42 0 00.806 1.946 3.42 3.42 0 010 4.438 3.42 3.42 0 00-.806 1.946 3.42 3.42 0 01-3.138 3.138 3.42 3.42 0 00-1.946.806 3.42 3.42 0 01-4.438 0 3.42 3.42 0 00-1.946-.806 3.42 3.42 0 01-3.138-3.138 3.42 3.42 0 00-.806-1.946 3.42 3.42 0 010-4.438 3.42 3.42 0 00.806-1.946 3.42 3.42 0 013.138-3.138z"
                            />
                        }
                    />

                    <FeatureCard
                        iconBg="bg-emerald-50"
                        iconColor="text-fundinv-success"
                        title="Real-time P&L tracking"
                        description="View daily, monthly, and year-to-date returns with transaction history at a glance."
                        icon={
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 013 19.875v-6.75zM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V8.625zM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 01-1.125-1.125V4.125z"
                            />
                        }
                    />

                    <FeatureCard
                        iconBg="bg-amber-50"
                        iconColor="text-fundinv-warning"
                        title="Audited & compliant"
                        description="Every action is logged with complete traceability for operational and regulatory review."
                        icon={
                            <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.746 3.746 0 011.043 3.296A3.745 3.745 0 0121 12z"
                            />
                        }
                    />
                </div>
            </section>
        </Layout>
    );
}

function FeatureCard({
    icon,
    iconBg,
    iconColor,
    title,
    description,
}: {
    icon: React.ReactNode;
    iconBg: string;
    iconColor: string;
    title: string;
    description: string;
}) {
    return (
        <div className="bg-white border border-fundinv-border rounded-xl p-6 shadow-sm hover:shadow-md transition">
            <div className={`w-10 h-10 ${iconBg} rounded-md flex items-center justify-center mb-4`}>
                <svg
                    className={`w-5 h-5 ${iconColor}`}
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                >
                    {icon}
                </svg>
            </div>

            <p className="text-sm font-semibold text-fundinv-primary mb-1.5">
                {title}
            </p>

            <p className="text-sm text-fundinv-muted leading-relaxed">
                {description}
            </p>
        </div>
    );
}
