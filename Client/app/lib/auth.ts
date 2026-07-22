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

const TOKEN_KEY = 'fundinv_token';

export function setToken(token: string): void {
    if (typeof window === 'undefined') return;
    localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
    if (typeof window === 'undefined') return null;
    return localStorage.getItem(TOKEN_KEY);
}

export function clearToken(): void {
    if (typeof window === 'undefined') return;
    localStorage.removeItem(TOKEN_KEY);
}

export function decodeToken(): { sub: string; email: string; role: string; full_name: string; claims: string[]; exp: number } | null {
    const token = getToken();
    if (!token) return null;
    try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        return {
            sub: payload.sub,
            email: payload.email,
            role: payload.role,
            full_name: payload.full_name || '',
            claims: payload.claims || [],
            exp: payload.exp,
        };
    } catch {
        return null;
    }
}

export function getUser(): User | null {
    const payload = decodeToken();
    if (!payload) return null;
    if (payload.exp * 1000 < Date.now()) {
        clearToken();
        return null;
    }
    const user: User = {
        id: payload.sub,
        email: payload.email,
        full_name: payload.full_name,
        role: payload.role as User['role'],
        is_active: true,
        claims: payload.claims,
        hasClaim(claim: string): boolean {
            return this.claims.includes(claim);
        },
        inRole(role: string): boolean {
            return this.role === role;
        },
    };
    return user;
}

export function clearAuth(): void {
    clearToken();
}

export function isAuthenticated(): boolean {
    return decodeToken() !== null;
}

export function getDashboardPath(role: User['role']): string {
    switch (role) {
        case 'admin':
            return '/dashboard/admin';
        case 'operations':
            return '/dashboard/operations';
        case 'manager':
            return '/dashboard/manager';
        case 'investor':
            return '/dashboard/investor';
        default:
            return '/';
    }
}
