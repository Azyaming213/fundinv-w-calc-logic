'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getUser, clearAuth, User } from '../lib/auth';
import { api } from '../lib/api';
import Link from 'next/link';

export default function Header() {
    const router = useRouter();
    const [user, setUser] = useState<User | null>(null);
    const [mounted, setMounted] = useState(false);
    const [menuOpen, setMenuOpen] = useState(false);

    useEffect(() => {
        setMounted(true);
        setUser(getUser());
    }, []);

    const handleSignIn = () => {
        router.push('/login');
    };

    const handleLogout = async () => {
        try {
            await api.post('/api/auth/logout');
        } catch {
            // Even if logout endpoint fails, clear local state
        }
        clearAuth();
        setUser(null);
        setMenuOpen(false);
        router.push('/');
    };

    return (
        <nav className="bg-white border-b border-fundinv-border">
            <div className="max-w-6xl mx-auto px-8 py-4 flex items-center justify-between">
                <div className="flex items-center gap-2.5">
                    <Link href="/" className="text-lg font-semibold text-fundinv-primary tracking-tight">
                        <div className="flex items-center gap-2">
                            <div className="w-8 h-8 bg-fundinv-primary rounded-md flex items-center justify-center">
                                <svg className="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path
                                        strokeLinecap="round"
                                        strokeLinejoin="round"
                                        strokeWidth={2.5}
                                        d="M3 3v18h18M7 14l4-4 4 4 5-5"
                                    />
                                </svg>
                            </div>

                            <span className="text-lg font-semibold text-fundinv-primary tracking-tight">
                                FundInv
                            </span>
                        </div>
                    </Link>
                </div>

                {mounted && user ? (
                    <div className="relative">
                        <button
                            onClick={() => setMenuOpen(!menuOpen)}
                            className="flex items-center gap-2 px-3 py-2 text-sm font-medium text-fundinv-primary border border-fundinv-border rounded-md hover:bg-fundinv-surface transition"
                        >
                            <div className="w-6 h-6 bg-fundinv-primary text-white rounded-full flex items-center justify-center text-xs font-semibold">
                                {user.full_name.charAt(0).toUpperCase()}
                            </div>
                            <span>{user.full_name}</span>
                            <span className="text-xs text-fundinv-muted px-1.5 py-0.5 bg-fundinv-surface rounded">
                                {user.role}
                            </span>
                            <svg className="w-4 h-4 text-fundinv-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                            </svg>
                        </button>

                        {menuOpen && (
                            <>
                                <div
                                    className="fixed inset-0 z-10"
                                    onClick={() => setMenuOpen(false)}
                                />
                                <div className="absolute right-0 mt-2 w-56 bg-white border border-fundinv-border rounded-md shadow-lg z-20">
                                    <div className="px-4 py-3 border-b border-fundinv-border">
                                        <p className="text-sm font-medium text-fundinv-primary">{user.full_name}</p>
                                        <p className="text-xs text-fundinv-muted truncate">{user.email}</p>
                                    </div>
                                    <Link
                                        href="/dashboard/security"
                                        onClick={() => setMenuOpen(false)}
                                        className="block w-full px-4 py-2 text-left text-sm text-fundinv-primary hover:bg-fundinv-surface transition"
                                    >
                                        Account security
                                    </Link>
                                    <button
                                        onClick={handleLogout}
                                        className="w-full px-4 py-2 text-left text-sm text-fundinv-danger hover:bg-fundinv-surface transition"
                                    >
                                        Sign out
                                    </button>
                                </div>
                            </>
                        )}
                    </div>
                ) : (
                    <div className="flex items-center gap-3">
                        <span className="text-xs text-fundinv-muted hidden sm:inline">Existing investor?</span>
                        <button
                            onClick={handleSignIn}
                            className="px-4 py-2 text-sm font-medium bg-fundinv-primary text-white rounded-md hover:bg-fundinv-primary-hover transition"
                        >
                            Sign in
                        </button>
                    </div>
                )}
            </div>
        </nav >
    );
}
