"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState, type RefObject } from "react";
import { Flask } from "@phosphor-icons/react";
import { dateTime, decidableApprovals } from "@/lib/operations";
import { OperationsProvider, useOperations } from "./operations/OperationsProvider";
import { useAnalyst } from "./operations/useAnalyst";
import { currentNavItem } from "./console/nav";
import { SearchDialog } from "./console/SearchDialog";
import { Sidebar } from "./console/Sidebar";
import { Topbar } from "./console/Topbar";

export { LensMark } from "./console/LensMark";

/** Keeps Tab inside the open mobile drawer and closes it on Escape; focus returns to the trigger. */
function useDrawerFocus(
  open: boolean,
  close: () => void,
  drawerRef: RefObject<HTMLElement | null>,
  triggerRef: RefObject<HTMLElement | null>,
) {
  useEffect(() => {
    if (!open) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const trigger = triggerRef.current;
    const links = drawerRef.current?.querySelectorAll<HTMLAnchorElement>("a");
    links?.[0]?.focus();
    function trap(event: KeyboardEvent) {
      if (event.key === "Escape") {
        close();
        return;
      }
      if (event.key !== "Tab" || !links?.length) return;
      const first = links[0];
      const last = links[links.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
    window.addEventListener("keydown", trap);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", trap);
      trigger?.focus();
    };
  }, [open, close, drawerRef, triggerRef]);
}

function Workspace({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const analyst = useAnalyst();
  const { snapshot, error, connected, refresh } = useOperations();
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const navigationRef = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const closeMenu = useCallback(() => setMenuOpen(false), []);
  const current = currentNavItem(pathname);
  const live = connected && !error;

  useDrawerFocus(menuOpen, closeMenu, navigationRef, menuButton);

  const openSearch = useCallback(() => {
    setQuery("");
    dialog.current?.showModal();
    search.current?.focus();
  }, []);

  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        openSearch();
      }
      if (event.key === "Escape") setMenuOpen(false);
    }
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown", keyboard);
  }, [openSearch]);

  return (
    <div className="ops-shell">
      <a className="skip-link" href="#workspace">
        Skip to workspace
      </a>
      {menuOpen && <button className="menu-overlay" aria-label="Close navigation" onClick={closeMenu} />}
      <Sidebar
        open={menuOpen}
        current={current}
        pendingReview={snapshot?.counts.pending_review}
        approvals={decidableApprovals(snapshot, analyst).length}
        onNavigate={closeMenu}
        navigationRef={navigationRef}
      />
      <div className="ops-main" inert={menuOpen}>
        <Topbar
          menuOpen={menuOpen}
          onToggleMenu={() => setMenuOpen(!menuOpen)}
          menuButtonRef={menuButton}
          sectionLabel={current?.label ?? "Investigation"}
          analyst={analyst}
          snapshot={snapshot}
          live={live}
          hasError={Boolean(error)}
          onSearch={openSearch}
        />
        <div className="ops-environment">
          <Flask size={13} />
          <strong>Simulation mode</strong>
          <span>Synthetic payments and bank responses. Test accounts only.</span>
          <span className="snapshot-stamp">
            {snapshot ? `${dateTime(snapshot.as_of)} IST · #${snapshot.cursor}` : "Connecting to ledger…"}
          </span>
        </div>
        {(error || (!connected && snapshot)) && (
          <div className="ops-warning" role="status">
            <span>{error ?? "Recovering live connection. Showing the latest available snapshot."}</span>
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
          <footer className="workspace-footnote">
            <span>FraudLens · Decisions backed by an auditable record.</span>
            <span>UPI / Net banking / Cards / ATMs</span>
          </footer>
        </main>
      </div>
      <SearchDialog
        dialogRef={dialog}
        inputRef={search}
        snapshot={snapshot}
        query={query}
        onQueryChange={setQuery}
      />
    </div>
  );
}

export default function ConsoleShell({ children }: { children: React.ReactNode }) {
  return (
    <OperationsProvider>
      <Workspace>{children}</Workspace>
    </OperationsProvider>
  );
}
