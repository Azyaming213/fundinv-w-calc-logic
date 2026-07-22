import { getToken, clearAuth } from './auth';
import type { ApiError } from './types';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });

  if (response.status === 401) {
    const onLoginPage = typeof window !== 'undefined' && window.location.pathname === '/login';

    if (onLoginPage) {
      // A 401 on the login page means wrong credentials, not an expired session.
      // Let the actual backend error message pass through below.
      const json = await response.json().catch(() => ({}));
      throw {
        status: 401,
        message: json.detail || 'Invalid email or password',
      } as ApiError;
    }

    // A 401 anywhere else means the session token is invalid or expired.
    clearAuth();
    if (typeof window !== 'undefined') {
      window.location.href = '/login?expired=true';
    }
    throw { status: 401, message: 'Session expired' } as ApiError;
  }

  const json = await response.json();

  if (!response.ok) {
    let message = 'Request failed';
    const detail = json.detail;
    if (typeof detail === 'string') {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail.map((e: any) => `${e.loc ? e.loc.join('.') : ''}: ${e.msg}`).join('; ');
    }
    throw {
      status: response.status,
      message: message,
    } as ApiError;
  }

  if (json.success === false) {
    throw {
      status: response.status,
      message: json.error?.message || 'Request failed',
    } as ApiError;
  }

  return json.data as T;
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
};

export type { ApiError };
