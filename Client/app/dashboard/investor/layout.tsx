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
    label: 'Portfolio',
    href: '/dashboard/investor',
    claim: CLAIMS.readOwnPortfolio,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" />
      </svg>
    ),
  },
  {
    label: 'Funds',
    href: '/dashboard/investor/funds',
    claim: CLAIMS.readFunds,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 7h8m0 0v8m0-8l-8 8-4-4-6 6" />
      </svg>
    ),
  },
  {
    label: 'Fund Flows',
    href: '/dashboard/investor/fund-flows',
    claim: CLAIMS.readOwnFundFlows,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    label: 'P&L Allocations',
    href: '/dashboard/investor/valuations',
    claim: CLAIMS.readOwnPortfolio,
    icon: <span className="text-xs">NAV</span>,
  },
  {
    label: 'Articles',
    href: '/dashboard/investor/articles',
    claim: CLAIMS.readArticles,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z" />
      </svg>
    ),
  },
  {
    label: 'Feedback',
    href: '/dashboard/investor/feedback',
    claim: CLAIMS.readOwnFeedback,
    icon: <span className="text-xs">FB</span>,
  },
];

export default function InvestorLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const user = typeof window !== 'undefined' ? getUser() : null;
  const userClaims = user?.claims || [];

  const visibleTabs = tabs.filter((tab) => {
    if (!tab.claim) return true;
    return userClaims.includes(tab.claim);
  });

  return (
    <AuthGuard allowedRoles={[ROLES.INVESTOR]}>
      <Layout>
        <div className="max-w-6xl mx-auto px-8">
          <nav className="flex gap-1 border-b border-fundinv-border -mb-px">
            {visibleTabs.map((tab) => {
              const isActive =
                tab.href === '/dashboard/investor'
                  ? pathname === '/dashboard/investor'
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
