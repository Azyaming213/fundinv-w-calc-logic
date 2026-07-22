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
    label: 'Dashboard',
    href: '/dashboard/operations',
    claim: CLAIMS.readDashboard,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0a1 1 0 01-1-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 01-1 1" />
      </svg>
    ),
  },
  {
    label: 'Fund Flows',
    href: '/dashboard/operations/fund-flows',
    claim: CLAIMS.readAllFundFlows,
    icon: (
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
  },
  {
    label: 'Fund Reviews',
    href: '/dashboard/operations/fund-reviews',
    claim: CLAIMS.reviewFunds,
    icon: <span className="text-xs">FR</span>,
  },
  {
    label: 'Audit Logs',
    href: '/dashboard/operations/audit-logs',
    claim: CLAIMS.readAuditLogs,
    icon: <span className="text-xs">AL</span>,
  },
  {
    label: 'Feedback',
    href: '/dashboard/operations/feedback',
    claim: CLAIMS.manageFeedback,
    icon: <span className="text-xs">FB</span>,
  },
  {
    label: 'Invite Requests',
    href: '/dashboard/operations/invite-requests',
    claim: CLAIMS.requestInvites,
    icon: <span className="text-xs">IR</span>,
  },
];

export default function OperationsLayout({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const user = typeof window !== 'undefined' ? getUser() : null;
  const userClaims = user?.claims || [];

  const visibleTabs = tabs.filter((tab) => {
    if (!tab.claim) return true;
    return userClaims.includes(tab.claim);
  });

  return (
    <AuthGuard allowedRoles={[ROLES.OPERATIONS]}>
      <Layout>
        <div className="max-w-6xl mx-auto px-8">
          <nav className="flex gap-1 border-b border-fundinv-border -mb-px">
            {visibleTabs.map((tab) => {
              const isActive =
                tab.href === '/dashboard/operations'
                  ? pathname === '/dashboard/operations'
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
