import * as React from 'react';
import { useTranslation } from 'react-i18next';
import { Toaster as Sonner } from 'sonner';

type ToasterProps = React.ComponentProps<typeof Sonner>;

/** Sonner reads these custom properties, so every toast (plain or rich) follows the design tokens. */
const tokenStyle = {
  fontFamily: 'var(--font-sans)',
  '--border-radius': 'var(--radius-lg)',
  '--normal-bg': 'var(--c-bg-elevated)',
  '--normal-text': 'var(--c-fg)',
  '--normal-border': 'var(--c-border-strong)',
  '--success-bg': 'var(--c-success-bg)',
  '--success-text': 'var(--c-success-fg)',
  '--success-border': 'var(--c-success-border)',
  '--info-bg': 'var(--c-info-bg)',
  '--info-text': 'var(--c-info-fg)',
  '--info-border': 'var(--c-info-border)',
  '--warning-bg': 'var(--c-warning-bg)',
  '--warning-text': 'var(--c-warning-fg)',
  '--warning-border': 'var(--c-warning-border)',
  '--error-bg': 'var(--c-danger-bg)',
  '--error-text': 'var(--c-danger-fg)',
  '--error-border': 'var(--c-danger-border)',
} as React.CSSProperties;

function Toaster({ style, ...props }: ToasterProps) {
  const { t } = useTranslation('shell');
  return (
    <Sonner
      className="toaster group"
      containerAriaLabel={t('toasts.region')}
      style={{ ...tokenStyle, ...style }}
      toastOptions={{
        // Sonner's own rules are unlayered, so the utilities need `!` to win.
        classNames: {
          actionButton: 'bg-primary! text-primary-foreground!',
          cancelButton: 'bg-muted! text-muted-foreground!',
        },
      }}
      {...props}
    />
  );
}

export { Toaster };
