# React Spark Template

> Plantilla profesional para React SPA con Feature-Sliced Design

![Build](https://img.shields.io/badge/build-passing-brightgreen)
![TypeScript](https://img.shields.io/badge/TypeScript-5.9-blue)
![React](https://img.shields.io/badge/React-19-61dafb)
![License](https://img.shields.io/badge/license-MIT-green)

A production-ready template for React Single-Page Applications built with **Feature-Sliced Design (FSD)** architecture. Designed to be the starting point for multiple production projects.

---

## Quick Start

```bash
# 1. Clone the template
git clone https://github.com/your-org/react-spark-template.git my-app
cd my-app

# 2. Install dependencies
npm install

# 3. Configure environment
cp .env.example .env
# Edit .env with your API URL

# 4. Start development server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## Architecture: Feature-Sliced Design

```
src/
├── app/         ← Layer 1: Initialization, providers, router, global styles
├── pages/       ← Layer 2: Composition of widgets/features per route
├── widgets/     ← Layer 3: Composed UI blocks (Header, Sidebar)
├── features/    ← Layer 4: User actions (auth, notifications)
├── entities/    ← Layer 5: Business objects (User, Product)
└── shared/      ← Layer 6: Reusable infrastructure (api, hooks, ui, lib)
```

### Import Rules (STRICT)

```
app  →  pages  →  widgets  →  features  →  entities  →  shared
```

| Rule                 | Description                                                   |
| -------------------- | ------------------------------------------------------------- |
| **Unidirectional**   | Each layer may ONLY import from layers below it               |
| **No cross-slice**   | `features/auth` must NOT import from `features/notifications` |
| **Barrel imports**   | Always import from `index.ts`, never from internal files      |
| **shared isolation** | `shared/` must NOT import from any other layer                |

### Slice Structure

Every slice follows this consistent internal structure:

```
slice-name/
├── ui/           # React components (presentational + smart)
├── model/        # Zustand stores, types, Zod schemas
├── api/          # TanStack Query hooks + Axios calls
├── lib/          # Internal utilities (not exported)
└── index.ts      # PUBLIC API — only what other layers need
```

---

## Tech Stack

| Technology            | Version | Purpose                              |
| --------------------- | ------- | ------------------------------------ |
| React                 | 19      | UI library                           |
| TypeScript            | 5.9     | Static typing (strict mode)          |
| Vite                  | 8       | Build tool + dev server              |
| React Router          | 7       | SPA routing with lazy loading        |
| TanStack Query        | 5       | Server state management              |
| Zustand               | 5       | Client state management              |
| shadcn/ui             | —       | UI component system (New York style) |
| Tailwind CSS          | 4       | Utility-first styling                |
| React Hook Form       | 7       | Form state management                |
| Zod                   | 4       | Schema validation (runtime + types)  |
| Axios                 | 1       | HTTP client with interceptors        |
| Sonner                | 2       | Toast notifications                  |
| Vitest                | 4       | Unit testing                         |
| React Testing Library | 16      | Component testing                    |
| ESLint                | 10      | Linting (flat config)                |
| Prettier              | 3       | Code formatting                      |
| Husky                 | 9       | Git hooks                            |
| lint-staged           | 16      | Pre-commit checks                    |

---

## Available Scripts

```bash
npm run dev          # Start development server (http://localhost:5173)
npm run build        # Type-check + production build
npm run preview      # Preview production build
npm run lint         # Run ESLint
npm run lint:fix     # Run ESLint with auto-fix
npm run format       # Format all files with Prettier
npm run format:check # Check formatting without writing
npm run test         # Run tests once (CI mode)
npm run test:watch   # Run tests in watch mode
npm run test:ui      # Run tests with Vitest UI
npm run test:coverage # Run tests with coverage report
```

---

## Environment Variables

Create a `.env` file based on `.env.example`:

| Variable        | Required | Default       | Description                                             |
| --------------- | -------- | ------------- | ------------------------------------------------------- |
| `VITE_API_URL`  | ✅ Yes   | —             | Backend API base URL (e.g. `http://localhost:3000/api`) |
| `VITE_APP_NAME` | No       | `React Spark` | Application display name                                |

All variables are validated at runtime with Zod in `src/shared/config/env.ts`. The app will throw an error at startup if required variables are missing or invalid.

---

## Routes

| Path         | Access    | Layout     | Page          |
| ------------ | --------- | ---------- | ------------- |
| `/`          | Public    | None       | HomePage      |
| `/login`     | Public    | AuthLayout | LoginPage     |
| `/register`  | Public    | AuthLayout | RegisterPage  |
| `/dashboard` | Protected | AppLayout  | DashboardPage |
| `/settings`  | Protected | AppLayout  | SettingsPage  |
| `*`          | Any       | None       | NotFoundPage  |

---

## How to Create New Slices

### New Feature

```bash
# Create the directory structure manually or use the Claude command:
# /new-feature my-feature

mkdir -p src/features/my-feature/{ui,model,api}
```

```typescript
// src/features/my-feature/index.ts (barrel export)
export { MyFeatureComponent } from './ui/MyFeatureComponent';
export { useMyFeatureStore } from './model/my-feature.store';
export { useMyFeatureMutation } from './api/my-feature.api';
```

**Rules:**

- Only import from `entities/` and `shared/`
- Never import from other features
- Export only public API through `index.ts`

### New Entity

```bash
mkdir -p src/entities/product/{ui,model,api}
```

```typescript
// src/entities/product/model/product.types.ts
export interface Product {
  id: string;
  name: string;
  price: number;
}
```

**Rules:**

- Only presentational UI (no business logic)
- API hooks are GET-only (mutations belong in features)
- Only import from `shared/`

### New Widget

```bash
mkdir -p src/widgets/data-table/{ui,model}
```

**Rules:**

- Compose features and entities
- May have local UI state in Zustand
- Never import from pages

### New Page

```bash
mkdir -p src/pages/products
```

```tsx
// src/pages/products/ProductsPage.tsx
export default function ProductsPage() {
  return <div>...</div>;
}
```

Then register in `src/app/router/index.tsx`:

```tsx
const ProductsPage = lazy(() => import('@/pages/products/ProductsPage'));

// Add to router config:
{
  path: '/products',
  element: <Suspense fallback={<PageLoader />}><ProductsPage /></Suspense>,
}
```

---

## Code Conventions

### TypeScript

- `strict: true` + `noUncheckedIndexedAccess: true` — no compromises
- ZERO `any` — use `unknown` + type narrowing
- `interface` for object shapes; `type` for unions and utilities
- `as const` instead of `enum`
- `import type` for type-only imports
- Zod schemas as single source of truth → `z.infer<typeof schema>`

### React Components

```tsx
// ✅ Correct: function declaration, explicit interface, named export
interface UserCardProps {
  user: User;
  className?: string;
}

export function UserCard({ user, className }: UserCardProps) {
  return <div className={cn('...', className)}>...</div>;
}

// ❌ Avoid: React.FC, arrow function as component, default export
const UserCard: React.FC<Props> = () => ...;
```

### State Management

- **TanStack Query** → server state (API responses, caching)
- **Zustand** → global client state (auth, theme, sidebar)
- **useState/useReducer** → local component state
- Never store server data in Zustand

### File Naming

| Type      | Convention                 | Example           |
| --------- | -------------------------- | ----------------- |
| Component | PascalCase                 | `UserCard.tsx`    |
| Hook      | kebab-case + `use-` prefix | `use-debounce.ts` |
| Store     | kebab-case + `.store.ts`   | `auth.store.ts`   |
| Schema    | kebab-case + `.schemas.ts` | `auth.schemas.ts` |
| API       | kebab-case + `.api.ts`     | `user.api.ts`     |
| Types     | kebab-case + `.types.ts`   | `user.types.ts`   |
| Test      | `__tests__/name.test.ts`   | `cn.test.ts`      |

### Imports

```typescript
// ✅ Always use @ alias
import { Button } from '@/shared/ui/button';
import { useAuthStore } from '@/features/auth';

// ❌ Never go up more than one level with relative paths
import { Button } from '../../shared/ui/button';
```

---

## Use as Template

### Option 1: GitHub Template

Click **"Use this template"** on GitHub to create a new repository with this structure.

### Option 2: Clone and reinitialize

```bash
git clone https://github.com/your-org/react-spark-template.git my-new-project
cd my-new-project
rm -rf .git
git init
git add .
git commit -m "feat: initial project setup from react-spark-template"
```

### After setup checklist

- [ ] Update `package.json` name and version
- [ ] Configure `.env` with your API URL
- [ ] Update app name in `VITE_APP_NAME`
- [ ] Replace mock data in `DashboardPage` with real queries
- [ ] Set up your backend API endpoints matching `src/features/auth/api/auth.api.ts`
- [ ] Customize theme colors in `src/app/styles/globals.css`
- [ ] Add your routes to `src/app/router/index.tsx`

---

## Project Structure (Complete)

```
react-spark-template/
├── public/
│   └── favicon.svg
├── src/
│   ├── app/
│   │   ├── providers/          # QueryProvider, ThemeProvider, RouterProvider, AppProvider
│   │   ├── router/
│   │   │   ├── guards/         # AuthGuard
│   │   │   ├── layouts/        # RootLayout, AppLayout, AuthLayout
│   │   │   └── index.tsx       # createBrowserRouter + lazy routes
│   │   └── styles/globals.css  # Tailwind v4 + CSS custom properties
│   ├── pages/                  # home, auth, dashboard, settings, not-found
│   ├── widgets/                # header, sidebar, theme-toggle
│   ├── features/               # auth (LoginForm, RegisterForm, store), notifications
│   ├── entities/               # user (UserAvatar, UserCard, types, api)
│   ├── shared/
│   │   ├── api/                # axios-instance, api-error, query-client
│   │   ├── config/             # env.ts (Zod-validated)
│   │   ├── hooks/              # use-debounce, use-media-query, use-disclosure
│   │   ├── lib/                # cn, format
│   │   ├── types/              # global utility types
│   │   └── ui/                 # shadcn/ui components
│   ├── test/setup.ts
│   └── main.tsx
├── .claude/                    # Claude Code context + slash commands
├── .vscode/                    # Editor settings + snippets
├── .env.example
├── eslint.config.js
├── vite.config.ts
└── tsconfig.json
```

---

## License

MIT © React Spark Template
