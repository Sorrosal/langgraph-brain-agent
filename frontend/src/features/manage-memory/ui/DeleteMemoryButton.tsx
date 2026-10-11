import { Trash2 } from 'lucide-react';
import { useState } from 'react';
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
  const [open, setOpen] = useState(false);
  const { mutate: deleteMemory, isPending } = useDeleteMemory();

  return (
    <>
      <Button
        variant="ghost"
        size="icon"
        aria-label="Delete memory"
        onClick={() => {
          setOpen(true);
        }}
      >
        <Trash2 className="h-4 w-4" />
      </Button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete this memory?</DialogTitle>
            <DialogDescription>The agent will no longer recall it.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => {
                setOpen(false);
              }}
            >
              Cancel
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
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
