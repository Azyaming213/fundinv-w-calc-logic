'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import Layout from '../../components/Layout';
import AuthGuard from '../../components/AuthGuard';
import { ROLES, CLAIMS } from '../../lib/appconstants';
import { getUser } from '../../lib/auth';

const tabs = [
  {
    label: 'Investors',
    href: '/dashboard/manager',
    claim: CLAIMS.readAssignedInvestors,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.5 2.5 0 11-5 0 2.5 2.5 0 015 0z" />
      </svg>
    ),
  },
  {
    label: 'Funds',
    href: '/dashboard/manager/funds',
    claim: CLAIMS.createFunds,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    label: 'Transactions',
    href: '/dashboard/manager/transactions',
    claim: CLAIMS.readTransactions,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
      </svg>
    ),
  },
  {
    label: 'Articles',
    href: '/dashboard/manager/articles',
    claim: CLAIMS.readArticles,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
      </svg>
    ),
  },
];

export default function ManagerLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const user = typeof window !== 'undefined' ? getUser() : null;
  const userClaims = user?.claims || [];

  const visibleTabs = tabs.filter((tab) => {
    if (!tab.claim) return true;
    return userClaims.includes(tab.claim);
  });

  return (
    <AuthGuard allowedRoles={[ROLES.MANAGER]}>
      <Layout>
        <div className="max-w-6xl mx-auto px-8">
          <nav className="flex gap-1 border-b border-fundinv-border -mb-px">
            {visibleTabs.map((tab) => {
              const isActive =
                tab.href === '/dashboard/manager'
                  ? pathname === '/dashboard/manager'
                  : pathname.startsWith(tab.href);

              return (
                <Link
                  key={tab.href}
                  href={tab.href}
                  className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition ${
                    isActive
                      ? 'border-fundinv-accent text-fundinv-accent'
                      : 'border-transparent text-fundinv-muted hover:text-fundinv-primary hover:border-fundinv-border'
                  }`}
                >
                  {tab.icon}
                  {tab.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div>{children}</div>
      </Layout>
    </AuthGuard>
  );
}
