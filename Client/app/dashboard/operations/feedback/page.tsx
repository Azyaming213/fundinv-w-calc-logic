'use client';

import { useEffect, useState } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import { api } from '../../../lib/api';

type Ticket = { id: number; email: string | null; subject: string; message: string; status: string; response: string | null };

export default function OperationsFeedbackPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const load = () => api.get<{ tickets: Ticket[] }>('/api/feedback').then((data) => setTickets(data.tickets || [])).catch(() => setTickets([]));
  useEffect(() => { load(); }, []);
  const resolve = async (ticket: Ticket) => { const response = window.prompt('Response to investor', ticket.response || ''); if (response === null) return; await api.patch(`/api/feedback/${ticket.id}`, { response, status: 'resolved' }); load(); };
  return <div className="max-w-6xl mx-auto px-8 py-8"><div className="mb-8"><h1 className="text-2xl font-semibold text-fundinv-primary">Investor Feedback</h1><p className="text-sm text-fundinv-muted mt-1">Respond to investor questions and support requests.</p></div><div className="space-y-4">{tickets.map((ticket) => <Card key={ticket.id}><div className="flex justify-between gap-4"><div><p className="text-xs text-fundinv-muted">{ticket.email || 'Investor'} · {ticket.status}</p><h2 className="font-semibold text-fundinv-primary mt-1">{ticket.subject}</h2><p className="text-sm text-fundinv-muted mt-2 whitespace-pre-wrap">{ticket.message}</p>{ticket.response && <p className="text-sm text-emerald-700 mt-3">Response: {ticket.response}</p>}</div>{ticket.status !== 'resolved' && <Button onClick={() => resolve(ticket)}>Respond</Button>}</div></Card>)}{tickets.length === 0 && <Card><p className="py-8 text-center text-sm text-fundinv-muted">No feedback tickets.</p></Card>}</div></div>;
}
