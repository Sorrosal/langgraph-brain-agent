import { useTranslation } from 'react-i18next';

/** Friendly, translated name of a tool; unknown tools keep their raw name. */
export function useToolLabel(): (toolName: string) => string {
  const { t } = useTranslation();
  return (toolName) => t(`common:tools.${toolName}`, { defaultValue: toolName });
}
