import { GITHUB_URL } from '@/shared/config/links';

export function LandingFooter() {
  return (
    <footer className="text-muted-foreground mt-8 border-t py-8 text-center text-sm">
      <p>
        Released under the MIT license.{' '}
        <a
          href={GITHUB_URL}
          target="_blank"
          rel="noreferrer"
          className="text-foreground underline underline-offset-4"
        >
          LangGraph Brain Agent on GitHub
        </a>
      </p>
    </footer>
  );
}
