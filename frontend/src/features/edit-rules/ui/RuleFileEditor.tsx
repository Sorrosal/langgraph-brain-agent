import { FileCode, Loader2 } from 'lucide-react';
import { useId, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Badge } from '@/shared/ui/badge';
import { Button } from '@/shared/ui/button';
import { Card } from '@/shared/ui/card';
import { Textarea } from '@/shared/ui/textarea';
import { useSaveRuleFile } from '../api/edit-rules.api';

interface RuleFileEditorProps {
  name: string;
  content: string;
  /** Non-admins see the YAML but cannot change it. */
  readOnly: boolean;
}

export function RuleFileEditor({ name, content, readOnly }: RuleFileEditorProps) {
  const { t } = useTranslation('brain');
  const errorId = useId();
  const [draft, setDraft] = useState(content);
  const { mutate: save, isPending, error, reset } = useSaveRuleFile();
  const dirty = draft !== content;

  return (
    <Card className="overflow-hidden">
      <div className="bg-subtle flex flex-wrap items-center justify-between gap-2 border-b px-4 py-2.5">
        <label
          htmlFor={`rules-${name}`}
          className="flex items-center gap-2 font-mono text-sm font-medium"
        >
          <FileCode className="text-muted-foreground size-4" aria-hidden />
          {name}
        </label>
        {readOnly ? (
          <Badge variant="outline">{t('rules.readOnly')}</Badge>
        ) : (
          dirty && <Badge variant="warning">{t('rules.files.unsaved')}</Badge>
        )}
      </div>
      <div className="flex flex-col gap-3 p-4">
        <Textarea
          id={`rules-${name}`}
          className="min-h-64 resize-y font-mono text-xs leading-relaxed md:text-xs"
          value={draft}
          readOnly={readOnly}
          spellCheck={false}
          aria-invalid={Boolean(error)}
          aria-describedby={error ? errorId : undefined}
          onChange={(e) => {
            setDraft(e.target.value);
            if (error) reset();
          }}
        />
        {error && (
          <div
            id={errorId}
            role="alert"
            className="border-danger-border bg-danger-bg text-danger-fg flex flex-col gap-1 rounded-[var(--radius-md)] border p-3 text-sm"
          >
            <p className="font-medium">{t('rules.files.errorTitle')}</p>
            <pre className="font-mono text-xs break-words whitespace-pre-wrap">{error.message}</pre>
          </div>
        )}
        {!readOnly && (
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <Button
              variant="ghost"
              className="h-11 sm:h-10"
              disabled={isPending || !dirty}
              onClick={() => {
                setDraft(content);
                reset();
              }}
            >
              {t('rules.files.discard')}
            </Button>
            <Button
              className="h-11 sm:h-10"
              disabled={isPending || !dirty}
              onClick={() => {
                save({ filename: name, content: draft });
              }}
            >
              {isPending && <Loader2 className="motion-safe:animate-spin" aria-hidden />}
              {t('rules.files.save', { name })}
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
}
