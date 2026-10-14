/// <reference types="vitest" />
import path from 'path';
import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react-swc';
import { defineConfig, loadEnv } from 'vite';

// Vendor chunk per package name. Small helper packages travel with their parent so a chunk never
// imports back from the app chunk (which would be a circular chunk dependency).
const VENDOR_CHUNKS: [RegExp, string][] = [
  [/^(react|react-dom|react-router|react-router-dom|scheduler|cookie|set-cookie-parser)$/, 'react'],
  [/^@radix-ui\//, 'radix'],
  [/^(i18next|react-i18next|html-parse-stringify|void-elements)$/, 'i18n'],
  [/^@tanstack\//, 'query'],
  [/^zod$/, 'zod'],
  [/^lucide-react$/, 'icons'],
  [
    /^(react-markdown|remark-.*|rehype-.*|micromark.*|mdast.*|unified|hast.*|unist.*|vfile.*|decode-named-character-reference|character-entities.*|devlop|trim-lines|trough|bail|is-plain-obj|property-information|space-separated-tokens|comma-separated-tokens|html-url-attributes|ccount|longest-streak|markdown-table|zwitch|stringify-entities|style-to-js|inline-style-parser|extend)$/,
    'markdown',
  ],
];

function vendorChunk(id: string): string | undefined {
  const marker = 'node_modules/';
  const at = id.lastIndexOf(marker);
  if (at === -1) return undefined;
  // innermost node_modules, so it also works with pnpm's nested layout
  const pkg = /^((?:@[^/]+\/)?[^/]+)/.exec(id.slice(at + marker.length))?.[1];
  if (!pkg) return undefined;
  return VENDOR_CHUNKS.find(([pattern]) => pattern.test(pkg))?.[1];
}

export default defineConfig(({ mode }) => ({
  base: loadEnv(mode, process.cwd(), 'VITE_').VITE_BASE_PATH ?? '/',
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    target: 'esnext',
    rollupOptions: {
      output: {
        // Stable vendor chunks so an app change does not invalidate the cached libraries.
        manualChunks: vendorChunk,
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
}));
