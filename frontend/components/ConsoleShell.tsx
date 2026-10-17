"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useSyncExternalStore } from "react";
import { clearSession, getStoredAnalyst } from "@/lib/auth";
import { dateTime } from "@/lib/operations";
import {
  OperationsProvider,
  useOperations,
} from "./operations/OperationsProvider";
const nav = [
  ["/dashboard", "Overview", "01"],
  ["/cases", "Investigations", "02"],
  ["/live", "Transactions", "03"],
  ["/network", "Connections", "04"],
  ["/bank", "Bank actions", "05"],
  ["/reports", "Reports", "06"],
  ["/audit", "Audit trail", "07"],
  ["/insights", "Controls & guidance", "08"],
];
const subscribe = () => () => {};
export function LensMark() {
  return (
    <svg width="27" height="27" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M6 3h20v7H13v5h11v7H13v7H6z" fill="currentColor" />
      <path d="m22 24 7 5" stroke="currentColor" strokeWidth="3" />
      <circle
        cx="21"
        cy="20"
        r="5"
        fill="var(--canvas)"
        stroke="currentColor"
        strokeWidth="2"
      />
    </svg>
  );
}
function Workspace({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const analyst = useSyncExternalStore(subscribe, getStoredAnalyst, () => null);
  const { snapshot, error, connected, refresh } = useOperations();
  return (
    <div className="ops-shell">
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      <aside className="ops-sidebar">
        <Link href="/" className="ops-brand">
          <LensMark />
          <span>
            FraudLens<small>Investigation workspace</small>
          </span>
        </Link>
        <nav aria-label="Main navigation">
          {nav.map(([href, label, n]) => (
            <Link
              key={href}
              href={href}
              aria-current={
                pathname === href || (href === "/cases" && pathname === "/case")
                  ? "page"
                  : undefined
              }
            >
              <span>{n}</span>
              {label}
              {href === "/cases" && snapshot ? (
                <b>{snapshot.counts.pending_review}</b>
              ) : null}
            </Link>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <strong>Local simulation</strong>
          <p>UPI · Net banking · Cards · ATMs</p>
          <p>Protective actions affect test accounts only.</p>
        </div>
      </aside>
      <div className="ops-main">
        <header className="ops-topbar">
          <span>Financial crime operations</span>
          <div className="topbar-session">
            <span
              className={
                connected && !error ? "connection good" : "connection warning"
              }
            >
              {connected && !error ? "Live connection" : "Reconnecting"}
            </span>
            <span>{analyst?.display_name ?? "Analyst"}</span>
            <button
              className="text-button"
              onClick={() => {
                clearSession();
                router.push("/login");
                router.refresh();
              }}
            >
              Sign out
            </button>
          </div>
        </header>
        <div className="ops-environment">
          <strong>SIMULATED ENVIRONMENT</strong>
          <span>All payments, accounts and bank responses are synthetic.</span>
          <span className="snapshot-stamp">
            {snapshot
              ? `Updated ${dateTime(snapshot.as_of)} IST · #${snapshot.cursor}`
              : "Connecting to operations…"}
          </span>
        </div>
        {(error || !connected) && (
          <div className="ops-warning" role="status">
            <span>
              {error ??
                "Recovering live connection. Showing the latest available snapshot."}
            </span>
            <button
              onClick={() => {
                void refresh().catch(() => {});
              }}
            >
              Refresh
            </button>
            <Link href="/login">Sign in again</Link>
          </div>
        )}
        <main id="workspace" className="ops-content">
          {children}
        </main>
      </div>
    </div>
  );
}
export default function ConsoleShell({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <OperationsProvider>
      <Workspace>{children}</Workspace>
    </OperationsProvider>
  );
}
