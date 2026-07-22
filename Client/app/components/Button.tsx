import { ButtonHTMLAttributes, ReactNode } from 'react';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger';
  children: ReactNode;
}

export default function Button({ variant = 'primary', children, className = '', ...props }: ButtonProps) {
  const variants = {
    primary: 'bg-fundinv-primary text-white hover:bg-fundinv-primary-hover',
    secondary: 'bg-white text-fundinv-primary border border-fundinv-border hover:bg-fundinv-surface',
    danger: 'bg-fundinv-danger text-white hover:opacity-90',
  };

  return (
    <button
      className={`px-4 py-2 text-sm font-medium rounded-md transition ${variants[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}