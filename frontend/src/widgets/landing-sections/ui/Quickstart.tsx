import { useTranslation } from 'react-i18next';
import { CodeBlock } from '@/shared/ui/code-block';
import { Section } from '@/shared/ui/section';
import { buildQuickstartCode } from '../model/quickstart';

export function Quickstart() {
  const { t } = useTranslation('landing');

  return (
    <Section
      id="quickstart"
      title={t('quickstart.title')}
      description={t('quickstart.description')}
    >
      <CodeBlock
        code={buildQuickstartCode((id) => t(`quickstart.steps.${id}`))}
        label={t('quickstart.codeLabel')}
      />
    </Section>
  );
}
