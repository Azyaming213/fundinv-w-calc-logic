'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { getUser, User } from '../lib/auth';

interface AuthGuardProps {
  children: React.ReactNode;
  allowedRoles?: Array<User['role']>;
  allowedClaims?: string[];
}

export default function AuthGuard({ children, allowedRoles, allowedClaims }: AuthGuardProps) {
  const router = useRouter();
  const pathname = usePathname();
  const [checking, setChecking] = useState(true);
  const [authorized, setAuthorized] = useState(false);

  useEffect(() => {
    const user = getUser();

    if (!user) {
      window.location.replace(`/login?from=${encodeURIComponent(pathname)}`);
      return;
    }

    if (allowedRoles && !allowedRoles.includes(user.role)) {
      window.location.replace('/unauthorized');
      return;
    }

    if (allowedClaims && allowedClaims.length > 0) {
      const hasClaim = allowedClaims.some((c: string) => user.hasClaim(c));
      if (!hasClaim) {
        window.location.replace('/unauthorized');
        return;
      }
    }

    setAuthorized(true);
    setChecking(false);
  }, [router, pathname, allowedRoles, allowedClaims]);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-fundinv-surface">
        <div className="text-sm text-fundinv-muted">Verifying access...</div>
      </div>
    );
  }

  if (!authorized) {
    return null;
  }

  return <>{children}</>;
}
