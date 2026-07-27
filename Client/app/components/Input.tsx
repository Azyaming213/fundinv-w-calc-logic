import { InputHTMLAttributes, forwardRef, useId } from 'react';

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

const Input = forwardRef<HTMLInputElement, InputProps>(({ label, error, helperText, className = '', ...props }, ref) => {
  const generatedId = useId();
  const inputId = props.id || generatedId;
  return (
    <div className="flex flex-col gap-1.5">
      {label && (
        <label htmlFor={inputId} className="text-sm font-medium text-fundinv-primary">
          {label}
        </label>
      )}
      <input
        id={inputId}
        ref={ref}
        className={`px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-fundinv-accent ${
          error ? 'border-fundinv-danger' : 'border-fundinv-border'
        } ${className}`}
        {...props}
      />
      {error && <span className="text-xs text-fundinv-danger">{error}</span>}
      {helperText && !error && <span className="text-xs text-fundinv-muted">{helperText}</span>}
    </div>
  );
});

Input.displayName = 'Input';

export default Input;
