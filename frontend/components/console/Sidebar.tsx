"use client";
import Link from "next/link";
import type { RefObject } from "react";
import { Flask, ShieldCheck, Stack } from "@phosphor-icons/react";
import { LensMark } from "./LensMark";
import { NAV, type NavItem } from "./nav";

type SidebarProps = {
  open: boolean;
  current: NavItem | undefined;
  pendingReview: number | undefined;
  approvals: number;
  onNavigate: () => void;
  navigationRef: RefObject<HTMLElement | null>;
};

export function Sidebar({ open, current, pendingReview, approvals, onNavigate, navigationRef }: SidebarProps) {
  function links(items: NavItem[], label: string) {
    return (
      <nav aria-label={label}>
        {items.map(({ href, label: text, icon: Icon }) => {
          const isCurrent = current?.href === href;
          return (
            <Link key={href} href={href} onClick={onNavigate} aria-current={isCurrent ? "page" : undefined}>
              <Icon size={18} weight={isCurrent ? "fill" : "regular"} />
              {text}
              {href === "/cases" && pendingReview !== undefined && <b>{pendingReview}</b>}
              {href === "/team" && approvals > 0 && (
                <b aria-label={`${approvals} approvals waiting for you`}>{approvals}</b>
              )}
            </Link>
          );
        })}
      </nav>
    );
  }

  return (
    <aside ref={navigationRef} className="ops-sidebar" id="workspace-navigation" data-open={open}>
      <Link href="/" className="ops-brand">
        <LensMark />
        <span>FraudLens<small>Fraud intelligence</small></span>
      </Link>
      <div className="workspace-picker">
        <Stack size={22} weight="duotone" />
        <span><strong>Analyst workspace</strong><small>Local environment</small></span>
      </div>
      <div className="nav-group-label">Workspace</div>
      {links(NAV.slice(0, 6), "Main navigation")}
      <div className="nav-group-label">Evidence & assurance</div>
      {links(NAV.slice(6), "Evidence and assurance")}
      <div className="sidebar-bottom">
        <div className="sidebar-sim">
          <Flask size={22} weight="duotone" />
          <strong>A safe place to investigate.</strong>
          <p>Four payment channels. Fictional accounts. Reversible bank actions.</p>
        </div>
        <div className="sidebar-footer"><ShieldCheck size={14} /><span>Analyst access</span><span>Local</span></div>
      </div>
    </aside>
  );
}
