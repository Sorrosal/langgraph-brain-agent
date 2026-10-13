import { Loader2, Trash2 } from 'lucide-react';
import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from '@/shared/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog';
import { useDeleteMemory } from '../api/manage-memory.api';

interface DeleteMemoryButtonProps {
  memoryId: string;
}

export function DeleteMemoryButton({ memoryId }: DeleteMemoryButtonProps) {
  const { t } = useTranslation('brain');
  const [open, setOpen] = useState(false);
  const { mutate: deleteMemory, isPending } = useDeleteMemory();

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        className="hover:text-danger-fg -my-1 -mr-1 size-11 shrink-0 sm:size-10"
        aria-label={t('memories.delete.label')}
        title={t('memories.delete.label')}
        onClick={() => {
          setOpen(true);
        }}
      >
        <Trash2 aria-hidden />
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('memories.delete.title')}</DialogTitle>
            <DialogDescription>{t('memories.delete.description')}</DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <Button
              variant="outline"
              onClick={() => {
                setOpen(false);
              }}
            >
              {t('common:actions.cancel')}
            </Button>
            <Button
              variant="destructive"
              disabled={isPending}
              onClick={() => {
                deleteMemory(memoryId, {
                  onSuccess: () => {
                    setOpen(false);
                  },
                });
              }}
            >
              {isPending && <Loader2 className="motion-safe:animate-spin" aria-hidden />}
              {t('common:actions.delete')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
