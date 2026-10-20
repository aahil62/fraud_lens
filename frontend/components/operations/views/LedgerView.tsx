"use client";
import { useEffect, useState } from "react";
import { CHANNELS, type Case, type Snapshot, type Transaction, channelName, claimCase, explainError, human, opsFetch } from "@/lib/operations";
import { useOperations } from "../OperationsProvider";
import { useAnalyst } from "../useAnalyst";
import { CaseTable, Loading, PageHeading, TransactionTable } from "../Primitives";
import ScenarioControls from "../ScenarioControls";

const PAGE_SIZE = 25;

export const QUEUE_VIEWS = [
  { value: "all", label: "All" },
  { value: "mine", label: "Mine" },
  { value: "unassigned", label: "Unassigned" },
  { value: "awaiting_approval", label: "Awaiting approval" },
  { value: "complaints", label: "Complaints" },
] as const;
type QueueView = (typeof QUEUE_VIEWS)[number]["value"];

/** Mirrors the API's view filter so a racing refresh never shows a stale row. */
export function inQueueView(item: Case, view: QueueView, username?: string) {
  if (view === "mine") return Boolean(username) && item.assignee === username;
  if (view === "unassigned") return !item.assignee;
  if (view === "awaiting_approval") return Boolean(item.pending_approval);
  if (view === "complaints") return item.case_type === "complaint";
  return true;
}

function StatusStrip({ snapshot, status, onSelect }: { snapshot: Snapshot | null; status: string; onSelect: (value: string) => void }) {
  const items = [
    { value: "", label: "All investigations", count: snapshot?.counts.cases },
    { value: "new", label: "Awaiting review", count: snapshot?.counts.pending_review },
    { value: "investigating", label: "Investigating", count: snapshot?.counts.investigating },
    { value: "escalated", label: "Escalated", count: snapshot?.counts.escalated },
    { value: "resolved", label: "Resolved", count: snapshot?.counts.resolved },
  ];
  return (
    <div className="queue-status-strip" aria-label="Filter investigation status">
      {items.map((item) => (
        <button key={item.value} aria-pressed={status === item.value} onClick={() => onSelect(item.value)}>
          <span>{item.label}</span>
          <strong>{item.count?.toLocaleString("en-IN") ?? "…"}</strong>
        </button>
      ))}
    </div>
  );
}

function StreamContext({ snapshot }: { snapshot: Snapshot }) {
  const running = snapshot.simulation_state.running;
  return (
    <div className="ledger-context">
      <span><span className={`connection-dot ${running ? "running" : ""}`} />Stream {running ? "running" : "paused"}</span>
      <span><strong>{snapshot.counts.posted}</strong> posted</span>
      <span><strong>{snapshot.counts.declined}</strong> declined</span>
      <span><strong>{snapshot.counts.pending_payments}</strong> pending</span>
    </div>
  );
}

export function LedgerView({ kind }: { kind: "cases" | "transactions" }) {
  const { snapshot, refresh } = useOperations();
  const analyst = useAnalyst();
  const [channel, setChannel] = useState("");
  const [status, setStatus] = useState("");
  const [view, setView] = useState<QueueView>("all");
  const [claiming, setClaiming] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{ items: Case[] | Transaction[]; total: number } | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
    if (channel) params.set("channel", channel);
    if (status && kind === "cases") params.set("status", status);
    if (kind === "cases" && view !== "all") params.set("view", view);
    void opsFetch<{ items: Case[] | Transaction[]; total: number }>(`/${kind}?${params}`)
      .then((value) => {
        if (cancelled) return;
        setData(value);
        setError("");
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load ledger.");
      });
    return () => { cancelled = true; };
  }, [kind, channel, status, view, offset, snapshot?.cursor, reload]);

  async function claim(item: Case) {
    setClaiming(item.case_id);
    try {
      await claimCase(item.case_id, item.version);
      setError("");
    } catch (err) {
      setError(explainError(err, snapshot?.team));
    } finally {
      setClaiming(null);
      setReload((n) => n + 1);
      await refresh().catch(() => {});
    }
  }

  function selectStatus(value: string) {
    setStatus(value);
    setOffset(0);
  }

  return (
    <div className="workspace-view ledger-view">
      <PageHeading
        title={kind === "cases" ? "Investigation queue" : "Transaction ledger"}
        description={kind === "cases"
          ? "Review evidence, make a verdict, and track its protective action."
          : "Continuous attempted payments and the bank simulator’s actual outcomes."}
      />
      {kind === "transactions" && <ScenarioControls />}
      {kind === "cases" && <StatusStrip snapshot={snapshot} status={status} onSelect={selectStatus} />}
      {kind === "cases" && (
        <div className="queue-view-filters" role="group" aria-label="Queue view">
          {QUEUE_VIEWS.map((item) => (
            <button key={item.value} aria-pressed={view === item.value} onClick={() => { setView(item.value); setOffset(0); }}>
              {item.label}
              {item.value === "awaiting_approval" && snapshot?.approvals?.length ? <b>{snapshot.approvals.length}</b> : null}
            </button>
          ))}
          <span className="muted">Sorted by agent priority</span>
        </div>
      )}
      {kind === "transactions" && snapshot && <StreamContext snapshot={snapshot} />}
      <section className="ops-section ledger-panel">
        <div className="filter-bar">
          <label>
            Channel
            <select value={channel} onChange={(e) => { setChannel(e.target.value); setOffset(0); }}>
              <option value="">All channels</option>
              {CHANNELS.map((c) => <option key={c} value={c}>{channelName(c)}</option>)}
            </select>
          </label>
          {kind === "cases" && (
            <label>
              Case status
              <select value={status} onChange={(e) => selectStatus(e.target.value)}>
                <option value="">All statuses</option>
                {["new", "investigating", "escalated", "resolved"].map((s) => <option key={s} value={s}>{human(s)}</option>)}
              </select>
            </label>
          )}
          <p>{data ? `${data.total.toLocaleString("en-IN")} matching records` : "Loading records…"}</p>
        </div>
        {error && <p className="form-error" role="alert">{error}</p>}
        {!data ? (
          <Loading />
        ) : kind === "cases" ? (
          <CaseTable
            cases={(data.items as Case[]).filter((item) => inQueueView(item, view, analyst?.username))}
            onClaim={(item) => { void claim(item); }}
            busyId={claiming}
          />
        ) : (
          <TransactionTable transactions={data.items as Transaction[]} />
        )}
        <div className="pagination">
          <span>{data?.total ? `${offset + 1}–${Math.min(offset + PAGE_SIZE, data.total)} of ${data.total}` : "0 records"}</span>
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>
          <button disabled={!data || offset + PAGE_SIZE >= data.total} onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
        </div>
      </section>
    </div>
  );
}
