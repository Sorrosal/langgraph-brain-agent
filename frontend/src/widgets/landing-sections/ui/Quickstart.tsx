import { CodeBlock } from '@/shared/ui/code-block';
import { Section } from '@/shared/ui/section';
import { QUICKSTART_CODE } from '../model/quickstart';

export function Quickstart() {
  return (
    <Section
      id="quickstart"
      title="Quickstart"
      description="Run the whole stack locally: PostgreSQL in Docker, the backend with uv, the frontend with npm."
    >
      <CodeBlock code={QUICKSTART_CODE} label="quickstart commands" />
    </Section>
  );
}
