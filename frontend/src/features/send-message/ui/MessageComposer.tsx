import { ArrowUp, LoaderCircle } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { KeyboardEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/shared/ui/button';
import { cn } from '@/shared/lib/cn';

const MAX_LENGTH = 8000;

interface MessageComposerProps {
  /** A run is active: the composer is locked. */
  busy: boolean;
  /** The run is paused on a human decision (changes the hint, still locked). */
  waitingApproval?: boolean;
  /** The request to send is in flight. */
  sending: boolean;
  /** Send `text`; call `onSent` once the server accepted it so the box is cleared. */
  onSend: (text: string, onSent: () => void) => void;
}

export function MessageComposer({
  busy,
  waitingApproval = false,
  sending,
  onSend,
}: MessageComposerProps) {
  const { t } = useTranslation('chat');
  const [text, setText] = useState('');
  const input = useRef<HTMLTextAreaElement>(null);
  const locked = busy || sending;
  const content = text.trim();

  // Hand the focus back when the assistant is done, so the next message can be typed at once.
  useEffect(() => {
    if (!locked) input.current?.focus();
  }, [locked]);

  function submit() {
    if (locked || !content) return;
    onSend(content, () => {
      setText('');
    });
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  }

  return (
    <form
      className="flex flex-col gap-1.5"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <div
        className={cn(
          'bg-elevated shadow-e2 focus-within:prism-ring flex items-end gap-2 rounded-[var(--radius-xl)] border p-2 pl-4 transition-shadow',
          busy && !waitingApproval && 'prism-ring',
        )}
      >
        <textarea
          ref={input}
          aria-label={t('composer.label')}
          value={text}
          rows={1}
          maxLength={MAX_LENGTH}
          disabled={busy}
          placeholder={
            waitingApproval
              ? t('composer.placeholderApproval')
              : busy
                ? t('composer.placeholderBusy')
                : t('composer.placeholder')
          }
          className="text-reading placeholder:text-faint [field-sizing:content] max-h-48 min-h-10 flex-1 resize-none bg-transparent py-2 focus:outline-none disabled:cursor-not-allowed"
          onChange={(event) => {
            setText(event.target.value);
          }}
          onKeyDown={onKeyDown}
        />
        <Button
          type="submit"
          size="icon"
          aria-label={t('composer.send')}
          disabled={locked || !content}
          className="shrink-0 rounded-full"
        >
          {sending || (busy && !waitingApproval) ? (
            <LoaderCircle className="animate-spin" />
          ) : (
            <ArrowUp />
          )}
        </Button>
      </div>
      <p className="text-faint text-2xs hidden px-4 sm:block">{t('composer.hint')}</p>
    </form>
  );
}
