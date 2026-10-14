import { LoaderCircle } from 'lucide-react';
import { useId, useState } from 'react';
import type { SyntheticEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { useRenameThread } from '@/entities/thread';
import type { Thread } from '@/entities/thread';
import { Button } from '@/shared/ui/button';
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from '@/shared/ui/dialog';
import { Input } from '@/shared/ui/input';

const MAX_TITLE = 120;

interface RenameThreadDialogProps {
  thread: Thread;
  onClose: () => void;
}

/** Mounted only while renaming: Enter saves, Esc cancels. */
export function RenameThreadDialog({ thread, onClose }: RenameThreadDialogProps) {
  const { t } = useTranslation('chat');
  const inputId = useId();
  const [title, setTitle] = useState(thread.title);
  const { mutate, isPending } = useRenameThread();
  const next = title.trim();
  const canSave = next.length > 0 && next !== thread.title && !isPending;

  function submit(event: SyntheticEvent) {
    event.preventDefault();
    if (!canSave) return;
    mutate(
      { id: thread.id, title: next },
      {
        onSuccess: onClose,
        onError: () => {
          toast.error(t('rename.failed'));
        },
      },
    );
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent aria-describedby={undefined}>
        <form onSubmit={submit} className="grid gap-4">
          <DialogHeader>
            <DialogTitle>{t('rename.title')}</DialogTitle>
          </DialogHeader>
          <div className="flex flex-col gap-1.5">
            <label htmlFor={inputId} className="text-sm font-medium">
              {t('rename.label')}
            </label>
            <Input
              id={inputId}
              value={title}
              maxLength={MAX_TITLE}
              placeholder={t('untitled')}
              onFocus={(event) => {
                event.currentTarget.select();
              }}
              onChange={(event) => {
                setTitle(event.target.value);
              }}
            />
          </div>
          <DialogFooter className="max-sm:gap-2">
            <Button type="button" variant="outline" className="max-sm:h-11" onClick={onClose}>
              {t('common:actions.cancel')}
            </Button>
            <Button type="submit" className="max-sm:h-11" disabled={!canSave}>
              {isPending && <LoaderCircle className="motion-safe:animate-spin" aria-hidden />}
              {t('common:actions.save')}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
