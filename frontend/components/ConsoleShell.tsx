"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { Bank, CaretDown, CaretRight, FileText, Flask, FolderOpen, Graph, List, ListChecks, MagnifyingGlass, ShieldCheck, SignOut, SquaresFour, Stack, Swap, X } from "@phosphor-icons/react";
import { clearSession, getStoredAnalyst } from "@/lib/auth";
import { channelName, dateTime, money } from "@/lib/operations";
import { OperationsProvider, useOperations } from "./operations/OperationsProvider";
const nav = [
  { href: "/dashboard", label: "Overview", icon: SquaresFour },
  { href: "/cases", label: "Investigations", icon: FolderOpen },
  { href: "/live", label: "Transactions", icon: Swap },
  { href: "/network", label: "Connections", icon: Graph },
  { href: "/bank", label: "Bank actions", icon: Bank },
  { href: "/reports", label: "Reports", icon: FileText },
  { href: "/audit", label: "Audit trail", icon: ListChecks },
  { href: "/insights", label: "Controls & guidance", icon: ShieldCheck },
];
const subscribe = () => () => {};
export function LensMark() {
  return <svg width="30" height="30" viewBox="0 0 30 30" fill="none" aria-hidden="true"><circle cx="12" cy="15" r="9" stroke="currentColor" strokeWidth="2.3"/><path d="M18 6a9 9 0 1 1 0 18" stroke="currentColor" strokeWidth="2.3"/><path d="M9 15h12" stroke="currentColor" strokeWidth="1.5"/></svg>;
}
function Workspace({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const analyst = useSyncExternalStore(subscribe, getStoredAnalyst, () => null);
  const { snapshot, error, connected, refresh } = useOperations();
  const [menuOpen, setMenuOpen] = useState(false);
  const [query, setQuery] = useState("");
  const dialog = useRef<HTMLDialogElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const navigationRef = useRef<HTMLElement>(null);
  const menuButton = useRef<HTMLButtonElement>(null);
  const current = nav.find(x => x.href === pathname || (x.href === "/cases" && pathname === "/case"));
  const name = analyst?.display_name ?? "Analyst";
  const initials = name.split(/[ .]+/).filter(Boolean).slice(0,2).map(x=>x[0]).join("");
  const results = snapshot?.cases.filter(x => `${x.case_id} ${x.account_id} ${channelName(x.channel)} ${x.verdict}`.toLowerCase().includes(query.toLowerCase())).slice(0,8) ?? [];
  function openSearch() { setQuery(""); dialog.current?.showModal(); search.current?.focus(); }
  useEffect(() => {
    if (!menuOpen) return;
    const previousOverflow = document.body.style.overflow;
    const trigger = menuButton.current;
    document.body.style.overflow = "hidden";
    const links = navigationRef.current?.querySelectorAll<HTMLAnchorElement>("a");
    links?.[0]?.focus();
    function trap(event: KeyboardEvent) {
      if (event.key === "Escape") { setMenuOpen(false); return; }
      if (event.key !== "Tab" || !links?.length) return;
      const first = links[0], last = links[links.length-1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    window.addEventListener("keydown",trap);
    return () => { document.body.style.overflow = previousOverflow; window.removeEventListener("keydown",trap); trigger?.focus(); };
  }, [menuOpen]);
  useEffect(() => {
    function keyboard(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") { event.preventDefault(); dialog.current?.showModal(); search.current?.focus(); }
      if (event.key === "Escape") setMenuOpen(false);
    }
    window.addEventListener("keydown", keyboard);
    return () => window.removeEventListener("keydown",keyboard);
  }, []);
  function navigation(items: typeof nav) {
    return <nav aria-label={items[0].href === "/dashboard" ? "Main navigation" : "Evidence and assurance"}>{items.map(({href,label,icon: Icon})=><Link key={href} href={href} onClick={()=>setMenuOpen(false)} aria-current={current?.href===href?"page":undefined}><Icon size={18} weight={current?.href===href?"duotone":"regular"}/>{label}{href==="/cases" && snapshot && <b>{snapshot.counts.pending_review}</b>}</Link>)}</nav>;
  }
  return <div className="ops-shell">
    <a className="skip-link" href="#workspace">Skip to workspace</a>
    {menuOpen && <button className="menu-overlay" aria-label="Close navigation" onClick={()=>setMenuOpen(false)}/>}
    <aside ref={navigationRef} className="ops-sidebar" id="workspace-navigation" data-open={menuOpen}>
      <Link href="/" className="ops-brand"><LensMark/><span>FraudLens<small>Fraud intelligence</small></span></Link>
      <div className="workspace-picker"><Stack size={23} weight="duotone"/><span><strong>Analyst workspace</strong><small>Local environment</small></span><CaretDown size={11}/></div>
      <div className="nav-group-label">Workspace</div>{navigation(nav.slice(0,5))}
      <div className="nav-group-label">Evidence & assurance</div>{navigation(nav.slice(5))}
      <div className="sidebar-bottom"><div className="sidebar-sim"><Flask size={23} weight="duotone"/><strong>A safe place to investigate.</strong><p>Four payment channels. Fictional accounts. Reversible bank actions.</p></div><div className="sidebar-footer"><ShieldCheck size={14}/><span>Analyst access</span><span>Local</span></div></div>
    </aside>
    <div className="ops-main" inert={menuOpen}>
      <header className="ops-topbar">
        <button ref={menuButton} className="mobile-menu-button" aria-label={menuOpen?"Close navigation":"Open navigation"} aria-expanded={menuOpen} aria-controls="workspace-navigation" onClick={()=>setMenuOpen(!menuOpen)}>{menuOpen?<X size={22}/>:<List size={22}/>}</button>
        <Link href="/" className="mobile-brand"><LensMark/>FraudLens</Link>
        <div className="breadcrumbs"><span>Workspace</span><CaretRight size={12}/><strong>{current?.label ?? "Investigation"}</strong></div>
        <div className="topbar-session">
          <button className="header-search" onClick={openSearch} aria-label="Search investigations"><MagnifyingGlass size={15}/><span>Search investigations</span><kbd>⌘ K</kbd></button>
          <span className={connected&&!error?"connection good":"connection warning"}>{connected&&!error?"System live":!snapshot&&!error?"Connecting":"Reconnecting"}</span>
          <details className="analyst-menu"><summary aria-label={`Account: ${name}`}><span className="analyst-avatar">{initials}</span><span>{name}</span><CaretDown size={11}/></summary><div className="analyst-dropdown"><strong>{name}</strong><small className="muted">Authenticated analyst</small><button onClick={()=>{clearSession();router.push("/login");router.refresh();}}><SignOut size={15}/>Sign out</button></div></details>
        </div>
      </header>
      <div className="ops-environment"><Flask size={13}/><strong>Simulation mode</strong><span>Synthetic payments and bank responses. Test accounts only.</span><span className="snapshot-stamp">{snapshot?`${dateTime(snapshot.as_of)} IST · #${snapshot.cursor}`:"Connecting to ledger…"}</span></div>
      {(error||(!connected&&snapshot))&&<div className="ops-warning" role="status"><span>{error??"Recovering live connection. Showing the latest available snapshot."}</span><button onClick={()=>{void refresh().catch(()=>{});}}>Refresh</button><Link href="/login">Sign in again</Link></div>}
      <main id="workspace" className="ops-content">{children}<footer className="workspace-footnote"><span>FraudLens · Decisions backed by an auditable record.</span><span>UPI / Net banking / Cards / ATMs</span></footer></main>
    </div>
    <dialog ref={dialog} className="search-dialog" aria-labelledby="search-heading" onClick={event=>{if(event.target===event.currentTarget)dialog.current?.close();}}>
      <h2 id="search-heading" className="sr-only">Search investigations</h2>
      <div className="search-dialog-header"><MagnifyingGlass size={21}/><input ref={search} value={query} onChange={e=>setQuery(e.target.value)} placeholder="Find a case, account or payment channel…" aria-label="Search cases"/><button onClick={()=>dialog.current?.close()} aria-label="Close search">Esc</button></div>
      <div className="search-results">{results.map(item=><Link href={`/case?case_id=${encodeURIComponent(item.case_id)}`} key={item.case_id} onClick={()=>dialog.current?.close()}><span><strong>{item.case_id}</strong><small>{channelName(item.channel)} · {item.account_id}</small></span><span className="numeric">{money(item.amount_minor)}</span></Link>)}{!results.length&&<p>No matching investigations. Try an account reference or payment channel.</p>}</div>
      <div className="search-help">Searches the latest {snapshot?.cases.length??0} investigations. Use the investigation queue for the complete ledger.</div>
    </dialog>
  </div>;
}
export default function ConsoleShell({children}:{children:React.ReactNode}) {return <OperationsProvider><Workspace>{children}</Workspace></OperationsProvider>;}
