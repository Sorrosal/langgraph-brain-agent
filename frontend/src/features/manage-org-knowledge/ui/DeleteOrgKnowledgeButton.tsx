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
import { useDeleteOrgKnowledge } from '../api/manage-org-knowledge.api';

interface DeleteOrgKnowledgeButtonProps {
  itemId: string;
}

export function DeleteOrgKnowledgeButton({ itemId }: DeleteOrgKnowledgeButtonProps) {
  const { t } = useTranslation('brain');
  const [open, setOpen] = useState(false);
  const { mutate: remove, isPending } = useDeleteOrgKnowledge();

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        className="hover:text-danger-fg -my-1 -mr-1 size-11 shrink-0 sm:size-10"
        aria-label={t('org.delete.label')}
        title={t('org.delete.label')}
        onClick={() => {
          setOpen(true);
        }}
      >
        <Trash2 aria-hidden />
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('org.delete.title')}</DialogTitle>
            <DialogDescription>{t('org.delete.description')}</DialogDescription>
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
                remove(itemId, {
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
