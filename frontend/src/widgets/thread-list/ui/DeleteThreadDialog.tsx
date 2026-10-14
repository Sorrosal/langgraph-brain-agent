import { LoaderCircle } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import { useDeleteThread } from '@/entities/thread';
import type { Thread } from '@/entities/thread';
import { ApiError } from '@/shared/api/api-error';
import { Button } from '@/shared/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog';

interface DeleteThreadDialogProps {
  thread: Thread;
  onClose: () => void;
  /** The thread is gone on the server. */
  onDeleted: (threadId: string) => void;
}

/** Mounted only while confirming. */
export function DeleteThreadDialog({ thread, onClose, onDeleted }: DeleteThreadDialogProps) {
  const { t } = useTranslation('chat');
  const { mutate, isPending } = useDeleteThread();

  function confirm() {
    mutate(thread.id, {
      onSuccess: () => {
        onDeleted(thread.id);
        onClose();
      },
      onError: (error) => {
        // 409 `thread_busy`: a run is still active.
        toast.error(
          ApiError.isApiError(error) && error.status === 409
            ? t('delete.busy')
            : t('delete.failed'),
        );
        onClose();
      },
    });
  }

  return (
    <Dialog
      open
      onOpenChange={(open) => {
        if (!open && !isPending) onClose();
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{t('delete.title')}</DialogTitle>
          <DialogDescription>
            {t('delete.description', { title: thread.title || t('untitled') })}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter className="max-sm:gap-2">
          <Button
            type="button"
            variant="outline"
            className="max-sm:h-11"
            disabled={isPending}
            onClick={onClose}
          >
            {t('common:actions.cancel')}
          </Button>
          <Button
            type="button"
            variant="destructive"
            className="max-sm:h-11"
            disabled={isPending}
            onClick={confirm}
          >
            {isPending && <LoaderCircle className="motion-safe:animate-spin" aria-hidden />}
            {t('delete.action')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
