'use client';

import { useState, useEffect } from 'react';
import { API_BASE } from '../lib/api';

export default function Footer() {
  const [backendStatus, setBackendStatus] = useState<'checking' | 'connected' | 'disconnected'>('checking');

  useEffect(() => {
    fetch(`${API_BASE}/api/test`)
      .then((res) => res.json())
      .then(() => setBackendStatus('connected'))
      .catch(() => setBackendStatus('disconnected'));
  }, []);

  return (
    <footer className="bg-white border-t border-fundinv-border">
      <div className="max-w-6xl mx-auto px-8 py-6 flex flex-col sm:flex-row items-center justify-between gap-4">
        <div className="text-xs text-fundinv-muted">
          FundInv · Investor portal · 2026
        </div>
        <div className="flex items-center gap-4 text-xs text-fundinv-muted">
          <div className="flex items-center gap-1.5 font-mono">
            <span className={`w-1.5 h-1.5 rounded-full ${
              backendStatus === 'connected' ? 'bg-fundinv-success' :
              backendStatus === 'disconnected' ? 'bg-fundinv-danger' : 'bg-fundinv-warning'
            }`}></span>
            <span>{
              backendStatus === 'checking' ? 'Connecting' :
              backendStatus === 'connected' ? 'Systems operational' : 'Backend offline'
            }</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
