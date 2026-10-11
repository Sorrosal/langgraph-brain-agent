import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Button } from '@/shared/ui/button';
import { Input } from '@/shared/ui/input';
import { useAddMemory } from '../api/manage-memory.api';
import { addMemorySchema } from '../model/memory-form.schemas';
import type { AddMemoryValues } from '../model/memory-form.schemas';

export function AddMemoryForm() {
  const { mutate: addMemory, isPending } = useAddMemory();
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AddMemoryValues>({
    resolver: zodResolver(addMemorySchema),
    defaultValues: { kind: 'fact', text: '' },
  });

  function onSubmit(values: AddMemoryValues) {
    addMemory(values, {
      onSuccess: () => {
        reset({ kind: values.kind, text: '' });
      },
    });
  }

  return (
    <form
      onSubmit={(e) => void handleSubmit(onSubmit)(e)}
      className="flex flex-col gap-2 sm:flex-row sm:items-start"
      noValidate
    >
      <select
        aria-label="Memory kind"
        className="border-input bg-background h-9 rounded-md border px-2 text-sm"
        {...register('kind')}
      >
        <option value="fact">fact</option>
        <option value="preference">preference</option>
        <option value="episode">episode</option>
      </select>
      <div className="flex-1">
        <Input
          aria-label="Memory text"
          placeholder="Something the agent should remember…"
          aria-invalid={Boolean(errors.text)}
          {...register('text')}
        />
        {errors.text && <p className="text-destructive mt-1 text-sm">{errors.text.message}</p>}
      </div>
      <Button type="submit" disabled={isPending}>
        Add memory
      </Button>
    </form>
  );
}
