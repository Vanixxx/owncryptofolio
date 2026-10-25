import { Activity, BarChart3, FileText, Home, LineChart, List, PieChart, Settings, Wallet } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export type NavItem = {
  to: string
  key: string // nav.<key>
  short?: string // shorter label for the phone tab bar
  icon: LucideIcon
  tab?: boolean // shown in the phone tab bar
  soon?: boolean // whole page belongs to the later roadmap
  group: 'main' | 'manage'
}

export const NAV: NavItem[] = [
  { to: '/', key: 'dashboard', short: 'dashboardShort', icon: Home, tab: true, group: 'main' },
  { to: '/holdings', key: 'holdings', icon: PieChart, tab: true, group: 'main' },
  { to: '/transactions', key: 'transactions', short: 'transactionsShort', icon: List, tab: true, group: 'main' },
  { to: '/prices', key: 'prices', icon: LineChart, tab: true, group: 'main' },
  { to: '/stats', key: 'stats', icon: BarChart3, group: 'main' },
  { to: '/sources', key: 'sources', icon: Wallet, group: 'manage' },
  { to: '/reports', key: 'reports', icon: FileText, group: 'manage' },
  { to: '/settings', key: 'settings', icon: Settings, group: 'manage' },
  { to: '/system', key: 'system', icon: Activity, group: 'manage' },
]
