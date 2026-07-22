import { ReactNode } from 'react';

interface CardProps {
  title?: string;
  children: ReactNode;
  footer?: ReactNode;
  className?: string;
}

export default function Card({ title, children, footer, className = '' }: CardProps) {
  return (
    <div className={`bg-white border border-fundinv-border rounded-lg ${className}`}>
      {title && (
        <div className="px-6 py-4 border-b border-fundinv-border">
          <h3 className="text-sm font-semibold text-fundinv-primary">{title}</h3>
        </div>
      )}
      <div className="px-6 py-4">
        {children}
      </div>
      {footer && (
        <div className="px-6 py-3 border-t border-fundinv-border bg-fundinv-surface rounded-b-lg">
          {footer}
        </div>
      )}
    </div>
  );
}