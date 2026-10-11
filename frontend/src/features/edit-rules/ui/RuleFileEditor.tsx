import { useState } from 'react';
import { Button } from '@/shared/ui/button';
import { Textarea } from '@/shared/ui/textarea';
import { useSaveRuleFile } from '../api/edit-rules.api';

interface RuleFileEditorProps {
  name: string;
  content: string;
  /** Non-admins see the YAML but cannot change it. */
  readOnly: boolean;
}

export function RuleFileEditor({ name, content, readOnly }: RuleFileEditorProps) {
  const [draft, setDraft] = useState(content);
  const { mutate: save, isPending, error, reset } = useSaveRuleFile();

  return (
    <div className="flex flex-col gap-2">
      <label htmlFor={`rules-${name}`} className="font-mono text-sm font-medium">
        {name}
      </label>
      <Textarea
        id={`rules-${name}`}
        className="min-h-48 font-mono text-xs md:text-xs"
        value={draft}
        readOnly={readOnly}
        spellCheck={false}
        onChange={(e) => {
          setDraft(e.target.value);
          if (error) reset();
        }}
      />
      {error && (
        <pre role="alert" className="text-destructive text-xs whitespace-pre-wrap">
          {error.message}
        </pre>
      )}
      {!readOnly && (
        <Button
          className="self-start"
          disabled={isPending || draft === content}
          onClick={() => {
            save({ filename: name, content: draft });
          }}
        >
          Save {name}
        </Button>
      )}
    </div>
  );
}
