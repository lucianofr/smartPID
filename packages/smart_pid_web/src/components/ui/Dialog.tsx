import { useEffect, useId, type ReactNode } from 'react';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: 'var(--sp-4)',
  zIndex: 1000,
};

const backdropStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0, 0, 0, 0.6)',
  border: 'none',
  padding: 0,
  margin: 0,
  cursor: 'default',
  zIndex: 0,
};

const panelStyle: React.CSSProperties = {
  position: 'relative',
  zIndex: 1,
  background: 'var(--surface-container, var(--surface))',
  color: 'var(--text)',
  border: '1px solid var(--border-strong, var(--border))',
  borderRadius: 'var(--radius-card)',
  width: 'min(640px, 100%)',
  maxHeight: '90vh',
  display: 'flex',
  flexDirection: 'column',
  boxShadow: '0 8px 32px rgba(0, 0, 0, 0.5)',
};

const headerStyle: React.CSSProperties = {
  padding: 'var(--sp-4)',
  borderBottom: '1px solid var(--border)',
  fontSize: 'var(--text-lg)',
  fontWeight: 'var(--fw-semibold)' as unknown as number,
};

const bodyStyle: React.CSSProperties = {
  padding: 'var(--sp-4)',
  overflowY: 'auto',
  display: 'flex',
  flexDirection: 'column',
  gap: 'var(--sp-3)',
};

const footerStyle: React.CSSProperties = {
  padding: 'var(--sp-3) var(--sp-4)',
  borderTop: '1px solid var(--border)',
  display: 'flex',
  justifyContent: 'flex-end',
  gap: 'var(--sp-2)',
};

export function Dialog({ open, onClose, title, children, footer }: DialogProps) {
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  const titleId = useId();

  if (!open) return null;

  return (
    <div style={overlayStyle}>
      <button
        type="button"
        aria-label="Fechar"
        style={backdropStyle}
        onClick={onClose}
        data-testid="dialog-backdrop"
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        style={panelStyle}
      >
        <header id={titleId} style={headerStyle}>
          {title}
        </header>
        <div style={bodyStyle}>{children}</div>
        {footer ? <footer style={footerStyle}>{footer}</footer> : null}
      </div>
    </div>
  );
}
