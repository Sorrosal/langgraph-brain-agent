import {
  Brain,
  Database,
  MessageSquare,
  Microscope,
  Settings,
  ShieldCheck,
  type LucideIcon,
} from 'lucide-react';

export type NavKey = 'chat' | 'approvals' | 'inspector' | 'brain' | 'data' | 'settings';

export interface NavItem {
  to: string;
  icon: LucideIcon;
  /** Key under `shell:nav.*` holding the translated label. */
  key: NavKey;
}

export const navItems: readonly NavItem[] = [
  { to: '/app/chat', icon: MessageSquare, key: 'chat' },
  { to: '/app/approvals', icon: ShieldCheck, key: 'approvals' },
  { to: '/app/inspector', icon: Microscope, key: 'inspector' },
  { to: '/app/brain', icon: Brain, key: 'brain' },
  { to: '/app/data', icon: Database, key: 'data' },
  { to: '/app/settings', icon: Settings, key: 'settings' },
];

/** The nav entry owning `pathname` (nested routes such as `/app/chat/:id` match their parent). */
export function findNavItem(pathname: string): NavItem | undefined {
  return navItems.find((item) => pathname === item.to || pathname.startsWith(`${item.to}/`));
}
