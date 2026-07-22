'use client';

import { useState, useEffect, useCallback } from 'react';
import Card from '../../../components/Card';
import Button from '../../../components/Button';
import { api } from '../../../lib/api';
import type { Article } from '../../../lib/types';

const categories = [
  { value: '', label: 'All' },
  { value: 'market', label: 'Market' },
  { value: 'tech', label: 'Tech' },
  { value: 'finance', label: 'Finance' },
  { value: 'etf', label: 'ETFs' },
];

export default function InvestorArticlesPage() {
  const [articles, setArticles] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [category, setCategory] = useState('');

  const fetchArticles = useCallback(async (cat: string) => {
    setLoading(true);
    setError(null);
    try {
      const params = cat ? `?category=${cat}` : '';
      const data = await api.get<{ articles: Article[] }>(`/api/articles/${params}`);
      setArticles(data.articles || []);
    } catch (err) {
      const message = (err as { message?: string }).message || 'Failed to load articles';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchArticles(category);
  }, [fetchArticles, category]);

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '';
    try {
      return new Date(dateStr).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric',
      });
    } catch {
      return '';
    }
  };

  return (
    <div className="max-w-6xl mx-auto px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-fundinv-primary">Investment Articles</h1>
        <p className="text-sm text-fundinv-muted mt-1">Latest market news and investment insights</p>
      </div>

      <div className="flex gap-2 mb-6">
        {categories.map((cat) => (
          <button
            key={cat.value}
            onClick={() => setCategory(cat.value)}
            className={`px-4 py-2 text-sm font-medium rounded-md border transition ${
              category === cat.value
                ? 'border-fundinv-accent bg-fundinv-accent text-white'
                : 'border-fundinv-border text-fundinv-muted hover:border-fundinv-primary hover:text-fundinv-primary'
            }`}
          >
            {cat.label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-16 text-center text-sm text-fundinv-muted">Loading articles...</div>
      ) : error ? (
        <Card>
          <div className="py-12 text-center">
            <p className="text-sm text-fundinv-danger mb-3">{error}</p>
            <Button variant="secondary" onClick={() => fetchArticles(category)}>Retry</Button>
          </div>
        </Card>
      ) : articles.length === 0 ? (
        <Card>
          <div className="py-12 text-center text-sm text-fundinv-muted">No articles found.</div>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {articles.map((article, idx) => (
            <Card key={idx} className="flex flex-col">
              <div className="flex-1">
                <div className="flex items-center gap-2 mb-3 flex-wrap">
                  <span className="px-2 py-0.5 text-xs font-medium rounded bg-fundinv-surface text-fundinv-muted capitalize">
                    {article.category}
                  </span>
                  {article.published_at && (
                    <span className="text-xs text-fundinv-muted">{formatDate(article.published_at)}</span>
                  )}
                </div>

                <h3 className="text-sm font-semibold text-fundinv-primary mb-2 leading-snug">
                  {article.title}
                </h3>

                {article.summary && (
                  <p className="text-xs text-fundinv-muted leading-relaxed mb-3 line-clamp-3">
                    {article.summary.replace(/<[^>]*>/g, '')}
                  </p>
                )}

                {article.tickers.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-3">
                    {article.tickers.map((ticker) => (
                      <span
                        key={ticker}
                        className="px-1.5 py-0.5 text-[10px] font-mono font-bold bg-blue-50 text-fundinv-accent rounded"
                      >
                        ${ticker}
                      </span>
                    ))}
                  </div>
                )}
              </div>

              <div className="pt-3 border-t border-fundinv-border flex items-center justify-between">
                <span className="text-[10px] text-fundinv-muted">{article.source}</span>
                <a
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs font-medium text-fundinv-accent hover:underline"
                >
                  Read more
                </a>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
