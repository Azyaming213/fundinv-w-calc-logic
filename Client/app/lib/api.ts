import { clearAuth } from './auth';
import type { ApiError } from './types';

// Production serves the API through the same origin (for example CloudFront ->
// ALB -> Nginx). Local development can still override this in Client/.env.local.
export const API_BASE = process.env.NEXT_PUBLIC_API_URL || '';

type ApiPayload = {
  success?: boolean;
  data?: unknown;
  detail?: unknown;
  error?: { message?: string };
};

async function readPayload(response: Response): Promise<ApiPayload | null> {
  const body = await response.text();
  if (!body.trim()) return {};

  try {
    return JSON.parse(body) as ApiPayload;
  } catch {
    return null;
  }
}

function unavailableError(status: number): ApiError {
  return {
    status,
    message: 'Service temporarily unavailable. Please try again.',
  } as ApiError;
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown
): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    credentials: 'include',
  });

  if (response.status === 401) {
    const onLoginPage = typeof window !== 'undefined' && window.location.pathname === '/login';

    if (onLoginPage) {
      // A 401 on the login page means wrong credentials, not an expired session.
      // Let the actual backend error message pass through below.
      const json = await readPayload(response);
      throw {
        status: 401,
        message: typeof json?.detail === 'string' ? json.detail : 'Invalid email or password',
      } as ApiError;
    }

    // A 401 anywhere else means the session token is invalid or expired.
    clearAuth();
    if (typeof window !== 'undefined') {
      window.location.href = '/login?expired=true';
    }
    throw { status: 401, message: 'Session expired' } as ApiError;
  }

  const json = await readPayload(response);
  if (!json) {
    throw unavailableError(response.status);
  }

  if (!response.ok) {
    let message = 'Request failed';
    const detail = json.detail;
    if (typeof detail === 'string') {
      message = detail;
    } else if (Array.isArray(detail)) {
      message = detail.map((entry: unknown) => {
        const error = entry as { loc?: Array<string | number>; msg?: string };
        return `${error.loc ? error.loc.join('.') : ''}: ${error.msg || 'Invalid value'}`;
      }).join('; ');
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
