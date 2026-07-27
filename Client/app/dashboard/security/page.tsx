'use client';

import { useEffect, useState } from 'react';
import AuthGuard from '../../components/AuthGuard';
import Layout from '../../components/Layout';
import Card from '../../components/Card';
import Button from '../../components/Button';
import Input from '../../components/Input';
import { api } from '../../lib/api';

type Me = { email: string; full_name: string; role: string; mfa_enabled: boolean };
type Setup = { secret: string; otpauth_uri: string; qr_code: string };

export default function SecurityPage() {
  const [me, setMe] = useState<Me | null>(null);
  const [setup, setSetup] = useState<Setup | null>(null);
  const [code, setCode] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refresh = async () => {
    const data = await api.get<Me>('/api/auth/me');
    setMe(data);
  };

  useEffect(() => { refresh().catch(() => setError('Unable to load security settings')); }, []);

  const beginSetup = async () => {
    setBusy(true); setError(null); setMessage(null);
    try { setSetup(await api.post<Setup>('/api/auth/mfa/setup')); }
    catch (err) { setError((err as { message?: string }).message || 'Unable to start MFA setup'); }
    finally { setBusy(false); }
  };

  const submitCode = async (disable = false) => {
    setBusy(true); setError(null); setMessage(null);
    try {
      await api.post(disable ? '/api/auth/mfa/disable' : '/api/auth/mfa/verify', { code });
      setMessage(disable ? 'Multi-factor authentication disabled.' : 'Multi-factor authentication enabled.');
      setCode(''); setSetup(null); await refresh();
    } catch (err) { setError((err as { message?: string }).message || 'Invalid authentication code'); }
    finally { setBusy(false); }
  };

  return (
    <AuthGuard>
      <Layout>
        <main className="max-w-2xl mx-auto px-6 py-10">
          <h1 className="text-2xl font-semibold text-fundinv-primary">Account security</h1>
          <p className="mt-1 mb-6 text-sm text-fundinv-muted">Protect your account with a time-based one-time password.</p>
          <Card>
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-medium text-fundinv-primary">Authenticator app</p>
                <p className="text-sm text-fundinv-muted">Status: {me?.mfa_enabled ? 'Enabled' : 'Not enabled'}</p>
              </div>
              {!me?.mfa_enabled && !setup && <Button onClick={beginSetup} disabled={busy}>Set up MFA</Button>}
            </div>

            {setup && (
              <div className="mt-6 border-t border-fundinv-border pt-6 space-y-4">
                <p className="text-sm text-fundinv-primary">Scan this QR code with Microsoft Authenticator, Google Authenticator, or another TOTP app.</p>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={`data:image/png;base64,${setup.qr_code}`} alt="MFA setup QR code" className="w-48 h-48 border border-fundinv-border rounded" />
                <div><p className="text-xs text-fundinv-muted">Manual setup key</p><code className="text-xs break-all">{setup.secret}</code></div>
              </div>
            )}

            {(setup || me?.mfa_enabled) && (
              <div className="mt-5 max-w-xs space-y-3">
                <Input label="Six-digit code" inputMode="numeric" pattern="[0-9]{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))} />
                <Button onClick={() => submitCode(Boolean(me?.mfa_enabled))} disabled={busy || code.length !== 6} variant={me?.mfa_enabled ? 'secondary' : 'primary'}>
                  {busy ? 'Verifying…' : me?.mfa_enabled ? 'Disable MFA' : 'Verify and enable'}
                </Button>
              </div>
            )}
            {message && <p className="mt-4 text-sm text-fundinv-success">{message}</p>}
            {error && <p className="mt-4 text-sm text-fundinv-danger">{error}</p>}
          </Card>
        </main>
      </Layout>
    </AuthGuard>
  );
}
