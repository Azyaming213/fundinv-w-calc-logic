'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import Card from '../../../../components/Card';
import Button from '../../../../components/Button';
import { api } from '../../../../lib/api';
import type { StockData } from '../../../../lib/types';

export default function StockDetailPage() {
  const params = useParams();
  const router = useRouter();
  const symbol = decodeURIComponent(params.symbol as string);

  const [stock, setStock] = useState<StockData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [view, setView] = useState<'overview' | 'chart'>('overview');

  useEffect(() => {
    if (symbol) {
      setLoading(true);
      setError(null);
      api.get<StockData>(`/api/funds/stock/${encodeURIComponent(symbol)}`)
        .then((data) => {
          setStock(data);
        })
        .catch((err) => {
          setError((err as { message?: string }).message || 'Failed to load stock data');
        })
        .finally(() => setLoading(false));
    }
  }, [symbol]);

  const fmt = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' }).format(n);
  const pctColor = (n: number) => (n > 0 ? 'text-fundinv-success' : n < 0 ? 'text-fundinv-danger' : 'text-fundinv-muted');

  const chartData = (stock?.bars || []).map((b) => ({
    date: b.t ? new Date(b.t).toLocaleDateString('en-US', { month: 'short', day: 'numeric' }) : '',
    price: b.c,
    ...b,
  }));

  if (loading) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-fundinv-border rounded" />
          <div className="h-64 bg-fundinv-border rounded" />
        </div>
      </div>
    );
  }

  if (error || !stock) {
    return (
      <div className="max-w-5xl mx-auto px-8 py-8">
        <Card>
          <div className="py-8 text-center">
            <p className="text-sm text-fundinv-danger mb-3">{error || 'Stock not found'}</p>
            <Button variant="secondary" onClick={() => router.back()}>Go Back</Button>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto px-8 py-8">
      <div className="flex items-center gap-4 mb-6">
        <button onClick={() => router.back()} className="text-fundinv-muted hover:text-fundinv-primary transition">
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
        </button>
        <div>
          <h1 className="text-2xl font-semibold text-fundinv-primary">{stock.symbol}</h1>
          <p className="text-sm text-fundinv-muted">{stock.name}</p>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card className="text-center">
          <p className="text-xs text-fundinv-muted mb-1">Price</p>
          <p className="text-xl font-bold text-fundinv-primary">{fmt(stock.price)}</p>
        </Card>
        <Card className="text-center">
          <p className="text-xs text-fundinv-muted mb-1">Change</p>
          <p className={`text-xl font-bold ${pctColor(stock.change_pct)}`}>
            {stock.change_amt > 0 ? '+' : ''}{fmt(stock.change_amt)} ({stock.change_pct > 0 ? '+' : ''}{stock.change_pct.toFixed(2)}%)
          </p>
        </Card>
        <Card className="text-center">
          <p className="text-xs text-fundinv-muted mb-1">High / Low</p>
          <p className="text-sm font-semibold text-fundinv-primary">
            {fmt(stock.daily_high)} / {fmt(stock.daily_low)}
          </p>
        </Card>
        <Card className="text-center">
          <p className="text-xs text-fundinv-muted mb-1">Volume</p>
          <p className="text-sm font-semibold text-fundinv-primary">{stock.daily_volume?.toLocaleString() || '—'}</p>
        </Card>
      </div>

      <div className="flex gap-2 mb-4">
        <Button variant={view === 'overview' ? 'primary' : 'secondary'} onClick={() => setView('overview')}>Overview</Button>
        <Button variant={view === 'chart' ? 'primary' : 'secondary'} onClick={() => setView('chart')}>Chart</Button>
      </div>

      {view === 'overview' ? (
        <Card title="Stock Details">
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><p className="text-fundinv-muted">Symbol</p><p className="font-semibold text-fundinv-primary">{stock.symbol}</p></div>
            <div><p className="text-fundinv-muted">Name</p><p className="font-semibold text-fundinv-primary">{stock.name}</p></div>
            <div><p className="text-fundinv-muted">Exchange</p><p className="font-semibold text-fundinv-primary">{stock.exchange || 'N/A'}</p></div>
            <div><p className="text-fundinv-muted">Asset Class</p><p className="font-semibold text-fundinv-primary capitalize">{stock.asset_class || 'N/A'}</p></div>
            <div><p className="text-fundinv-muted">Open</p><p className="font-semibold text-fundinv-primary">{fmt(stock.daily_open)}</p></div>
            <div><p className="text-fundinv-muted">Prev Close</p><p className="font-semibold text-fundinv-primary">{fmt(stock.prev_close)}</p></div>
            <div><p className="text-fundinv-muted">Day High</p><p className="font-semibold text-fundinv-success">{fmt(stock.daily_high)}</p></div>
            <div><p className="text-fundinv-muted">Day Low</p><p className="font-semibold text-fundinv-danger">{fmt(stock.daily_low)}</p></div>
            <div><p className="text-fundinv-muted">Volume</p><p className="font-semibold text-fundinv-primary">{stock.daily_volume?.toLocaleString()}</p></div>
            <div><p className="text-fundinv-muted">Price</p><p className="font-semibold text-fundinv-primary">{fmt(stock.price)}</p></div>
          </div>
        </Card>
      ) : (
        <Card title="Price History (90 Days)">
          {chartData.length === 0 ? (
            <div className="h-40 flex flex-col items-center justify-center gap-2 text-sm text-fundinv-muted">
              <p>Chart data unavailable</p>
              <p className="text-xs">Check your Alpaca API configuration</p>
            </div>
          ) : (
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} interval="preserveStartEnd" />
                  <YAxis domain={['auto', 'auto']} tick={{ fontSize: 11 }} tickFormatter={(v) => `$${v}`} />
                  <Tooltip
                    formatter={(value: number) => [`$${value.toFixed(2)}`, 'Price']}
                    contentStyle={{ fontSize: 12, borderRadius: 8, border: '1px solid #E2E8F0' }}
                  />
                  <Line type="monotone" dataKey="price" stroke="#2563EB" dot={false} strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>
      )}
    </div>
  );
}
