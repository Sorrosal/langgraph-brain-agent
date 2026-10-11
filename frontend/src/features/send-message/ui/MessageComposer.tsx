import { Send } from 'lucide-react';
import { useState } from 'react';
import type { KeyboardEvent } from 'react';
import { Button } from '@/shared/ui/button';
import { Textarea } from '@/shared/ui/textarea';
import { useSendMessage } from '../api/send-message.api';

interface MessageComposerProps {
  threadId: string;
  /** A run is active or waiting for approval. */
  disabled: boolean;
  onSent: () => void;
}

export function MessageComposer({ threadId, disabled, onSent }: MessageComposerProps) {
  const [text, setText] = useState('');
  const { mutate: send, isPending } = useSendMessage(threadId);
  const blocked = disabled || isPending;
  const content = text.trim();

  function submit() {
    if (blocked || !content) return;
    send(content, {
      onSuccess: () => {
        setText('');
        onSent();
      },
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
      className="flex items-end gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      <Textarea
        aria-label="Message"
        value={text}
        rows={2}
        maxLength={8000}
        disabled={disabled}
        placeholder={
          disabled ? 'Waiting for the assistant…' : 'Write a message (Shift+Enter for a new line)'
        }
        className="max-h-40 resize-none"
        onChange={(event) => {
          setText(event.target.value);
        }}
        onKeyDown={onKeyDown}
      />
      <Button type="submit" size="icon" aria-label="Send" disabled={blocked || !content}>
        <Send />
      </Button>
    </form>
  );
}
