"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { RefObject } from "react";
import { CaretDown, CaretRight, List, MagnifyingGlass, SignOut, X } from "@phosphor-icons/react";
import { logout } from "@/lib/auth";
import type { AnalystProfile } from "@/lib/types";
import type { Snapshot } from "@/lib/operations";
import { RoleChip } from "../operations/RoleChip";
import { TeamPresence } from "../operations/TeamPresence";
import { LensMark } from "./LensMark";

type TopbarProps = {
  menuOpen: boolean;
  onToggleMenu: () => void;
  menuButtonRef: RefObject<HTMLButtonElement | null>;
  sectionLabel: string;
  analyst: AnalystProfile | null;
  snapshot: Snapshot | null;
  live: boolean;
  hasError: boolean;
  onSearch: () => void;
};

function initialsOf(name: string) {
  return name
    .split(/[ .]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("");
}

function connectionLabel(live: boolean, snapshot: Snapshot | null, hasError: boolean) {
  if (live) return "System live";
  return !snapshot && !hasError ? "Connecting" : "Reconnecting";
}

export function Topbar(props: TopbarProps) {
  const { menuOpen, onToggleMenu, menuButtonRef, sectionLabel, analyst, snapshot, live, hasError, onSearch } =
    props;
  const router = useRouter();
  const name = analyst?.display_name ?? "Analyst";

  async function signOut() {
    await logout();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="ops-topbar">
      <button
        ref={menuButtonRef}
        className="mobile-menu-button"
        aria-label={menuOpen ? "Close navigation" : "Open navigation"}
        aria-expanded={menuOpen}
        aria-controls="workspace-navigation"
        onClick={onToggleMenu}
      >
        {menuOpen ? <X size={22} /> : <List size={22} />}
      </button>
      <Link href="/" className="mobile-brand">
        <LensMark size={22} />
        FraudLens
      </Link>
      <div className="breadcrumbs">
        <span>Workspace</span>
        <CaretRight size={12} />
        <strong>{sectionLabel}</strong>
      </div>
      <div className="topbar-session">
        <button className="header-search" onClick={onSearch} aria-label="Search investigations">
          <MagnifyingGlass size={15} />
          <span>Search investigations</span>
          <kbd>⌘ K</kbd>
        </button>
        {snapshot?.team && <TeamPresence team={snapshot.team} />}
        <span className={live ? "connection good" : "connection warning"}>
          {connectionLabel(live, snapshot, hasError)}
        </span>
        <details className="analyst-menu">
          <summary aria-label={`Account: ${name}`}>
            <span className="analyst-avatar">{initialsOf(name)}</span>
            <span>{name}</span>
            <CaretDown size={11} />
          </summary>
          <div className="analyst-dropdown">
            <strong>{name}</strong>
            <small className="muted">
              {analyst?.role ? <RoleChip role={analyst.role} /> : null} Authenticated analyst
            </small>
            <button onClick={() => void signOut()}>
              <SignOut size={15} />
              Sign out
            </button>
          </div>
        </details>
      </div>
    </header>
  );
}
