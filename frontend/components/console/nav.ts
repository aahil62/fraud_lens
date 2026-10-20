import {
  Bank,
  FileText,
  FolderOpen,
  Graph,
  ListChecks,
  ShieldCheck,
  SquaresFour,
  Swap,
  UsersThree,
} from "@phosphor-icons/react";

export const NAV = [
  { href: "/dashboard", label: "Overview", icon: SquaresFour },
  { href: "/cases", label: "Investigations", icon: FolderOpen },
  { href: "/team", label: "Team", icon: UsersThree },
  { href: "/live", label: "Transactions", icon: Swap },
  { href: "/network", label: "Connections", icon: Graph },
  { href: "/bank", label: "Bank actions", icon: Bank },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/audit", label: "Audit trail", icon: ListChecks },
  { href: "/insights", label: "Controls & guidance", icon: ShieldCheck },
];

export type NavItem = (typeof NAV)[number];

/** The case page belongs to the Investigations section. */
export function currentNavItem(pathname: string): NavItem | undefined {
  return NAV.find((item) => item.href === pathname || (item.href === "/cases" && pathname === "/case"));
}
