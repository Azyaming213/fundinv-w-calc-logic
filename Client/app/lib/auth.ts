export interface User {
    id: string;
    email: string;
    full_name: string;
    role: 'investor' | 'operations' | 'manager' | 'admin';
    is_active: boolean;
    claims: string[];
    hasClaim(claim: string): boolean;
    inRole(role: string): boolean;
}

type StoredUser = Omit<User, 'hasClaim' | 'inRole'>;
const USER_KEY = 'fundinv_user';

export function setSessionUser(user: StoredUser): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function getUser(): User | null {
    if (typeof window === 'undefined') return null;
    try {
        const stored = localStorage.getItem(USER_KEY);
        if (!stored) return null;
        const value = JSON.parse(stored) as StoredUser;
        return {
            ...value,
            claims: value.claims || [],
            hasClaim(claim: string) { return this.claims.includes(claim); },
            inRole(role: string) { return this.role === role; },
        };
    } catch {
        clearAuth();
        return null;
    }
}

// Kept temporarily for call-site compatibility; authentication tokens are
// HTTP-only cookies and are intentionally unavailable to JavaScript.
export function getToken(): null { return null; }

export function clearAuth(): void {
    if (typeof window !== 'undefined') localStorage.removeItem(USER_KEY);
}

export function isAuthenticated(): boolean { return getUser() !== null; }

export function getDashboardPath(role: User['role']): string {
    switch (role) {
        case 'admin': return '/dashboard/admin';
        case 'operations': return '/dashboard/operations';
        case 'manager': return '/dashboard/manager';
        case 'investor': return '/dashboard/investor';
        default: return '/';
    }
}
