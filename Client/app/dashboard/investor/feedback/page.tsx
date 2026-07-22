'use client';

import { useEffect, useState } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import Input from '../../../components/Input';
import { api } from '../../../lib/api';

type Ticket = { id: number; subject: string; message: string; status: string; response: string | null; created_at: string | null };

export default function InvestorFeedbackPage() {
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [subject, setSubject] = useState('');
  const [message, setMessage] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const load = () => api.get<{ tickets: Ticket[] }>('/api/feedback/mine').then((data) => setTickets(data.tickets || [])).catch(() => setTickets([]));
  useEffect(() => { load(); }, []);
  const submit = async (event: React.FormEvent) => { event.preventDefault(); try { await api.post('/api/feedback', { subject, message }); setSubject(''); setMessage(''); setNotice('Feedback submitted. Operations will respond by email and in this page.'); load(); } catch (err) { setNotice((err as { message?: string }).message || 'Unable to submit feedback'); } };
  return <div className="max-w-4xl mx-auto px-8 py-8"><div className="mb-8"><h1 className="text-2xl font-semibold text-fundinv-primary">Feedback</h1><p className="text-sm text-fundinv-muted mt-1">Contact the operations team about your account or transactions.</p></div><Card title="Send Feedback" className="mb-6"><form onSubmit={submit} className="space-y-4"><Input label="Subject" value={subject} onChange={(event) => setSubject(event.target.value)} required /><textarea value={message} onChange={(event) => setMessage(event.target.value)} required rows={5} placeholder="Describe your question or issue" className="w-full px-3 py-2 text-sm border border-fundinv-border rounded-md" />{notice && <p className="text-sm text-fundinv-muted">{notice}</p>}<Button type="submit">Submit Feedback</Button></form></Card><div className="space-y-4">{tickets.map((ticket) => <Card key={ticket.id}><p className="text-xs text-fundinv-muted">{ticket.status} · {ticket.created_at ? new Date(ticket.created_at).toLocaleString() : ''}</p><h2 className="font-semibold text-fundinv-primary mt-1">{ticket.subject}</h2><p className="text-sm text-fundinv-muted mt-2 whitespace-pre-wrap">{ticket.message}</p>{ticket.response && <p className="text-sm text-emerald-700 mt-3 whitespace-pre-wrap">Operations: {ticket.response}</p>}</Card>)}</div></div>;
}
