import { useQueryClient } from '@tanstack/react-query';
import { BellOff } from 'lucide-react';
import { useState } from 'react';
import type { ComponentProps } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import type { PendingInterrupt } from '@/entities/approval';
import { pendingApprovalKeys } from '@/entities/pending-approval';
import { useDismissRun } from '@/entities/thread';
import { Button } from '@/shared/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/shared/ui/dialog';

interface DismissApprovalsButtonProps {
  threadId: string;
  kind: PendingInterrupt['kind'];
  /** Accessible name when the visible "Dismiss" is not enough (e.g. in a list). */
  label?: string;
  disabled?: boolean;
  size?: ComponentProps<typeof Button>['size'];
  className?: string;
  /** Called before the request is sent, so the run is marked started first. */
  onSubmitting?: () => void;
  /** Called when the request fails, even after this button has unmounted. */
  onSubmitFailed?: () => void;
}

/**
 * Declines everything a thread is waiting on (rejects approvals / skips uncertain actions) after
 * a confirmation; the server resumes the run so the assistant can acknowledge.
 */
export function DismissApprovalsButton({
  threadId,
  kind,
  label,
  disabled = false,
  size,
  className,
  onSubmitting,
  onSubmitFailed,
}: DismissApprovalsButtonProps) {
  const { t } = useTranslation('approvals');
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const { mutate, isPending } = useDismissRun(threadId, {
    onSubmitting,
    onFailed: () => {
      onSubmitFailed?.();
      toast.error(t('dismiss.failed'));
      // Nothing may be pending any more (409): resync the queue.
      void queryClient.invalidateQueries({ queryKey: pendingApprovalKeys.all });
    },
    onDismissed: () => {
      void queryClient.invalidateQueries({ queryKey: pendingApprovalKeys.all });
    },
  });

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size={size}
        aria-label={label}
        className={className}
        disabled={disabled || isPending}
        onClick={() => {
          setOpen(true);
        }}
      >
        <BellOff aria-hidden />
        {t('dismiss.action')}
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t('dismiss.title')}</DialogTitle>
            <DialogDescription>
              {t(
                kind === 'approval_required'
                  ? 'dismiss.descriptionApproval'
                  : 'dismiss.descriptionUncertain',
              )}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="max-sm:gap-2">
            <Button
              type="button"
              variant="outline"
              className="max-sm:h-11"
              onClick={() => {
                setOpen(false);
              }}
            >
              {t('common:actions.cancel')}
            </Button>
            <Button
              type="button"
              className="max-sm:h-11"
              onClick={() => {
                setOpen(false);
                mutate();
              }}
            >
              {t('dismiss.confirm')}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
