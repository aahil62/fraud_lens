"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  CHANNELS,
  type Case,
  type Transaction,
  type Guidance,
  type Snapshot,
  channelName,
  claimCase,
  explainError,
  dateTime,
  human,
  money,
  opsFetch,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import { useAnalyst } from "./useAnalyst";
import {
  ActionLedger,
  CaseTable,
  Empty,
  Loading,
  CaseLink,
  PageHeading,
  ReportButtons,
  Timeline,
  TransactionTable,
} from "./Primitives";
import ScenarioControls from "./ScenarioControls";
import { ArrowRight, ArrowUpRight, Bank, ChartBar, CheckCircle, Clock, CreditCard, FileText, MagnifyingGlass, ShieldCheck, WarningCircle } from "@phosphor-icons/react";
import "@/app/workspace-views.css";
function ChannelChart({ snapshot }: { snapshot: Snapshot }) {
  const max = Math.max(1, ...snapshot.channels.map((row) => row.transactions));
  return <section className="ops-section channel-chart-panel">
    <div className="section-heading"><div><h2>Payment channels</h2><p>All recorded attempts, by channel</p></div><ChartBar size={22} aria-hidden="true" /></div>
    <div className="channel-chart" role="img" aria-label={snapshot.channels.map((row) => `${channelName(row.channel)}: ${row.transactions} payment attempts`).join("; ")}>
      {CHANNELS.map((channel) => {
        const row = snapshot.channels.find((item) => item.channel === channel);
        const count = row?.transactions ?? 0;
        return <div className="channel-chart-row" key={channel}><div><strong>{channelName(channel)}</strong><span>{count.toLocaleString("en-IN")}</span></div><div className="channel-bar-track"><span style={{ width: `${count / max * 100}%` }} /></div><small>{row?.cases ?? 0} cases <span>·</span> {row?.pending_review ?? 0} awaiting review <span>·</span> {row?.resolved ?? 0} resolved <span>·</span> {row?.declined ?? 0} declined</small></div>;
      })}
    </div>
    <Link href="/live" className="panel-footer-link">Explore transaction ledger <ArrowRight size={16} /></Link>
  </section>;
}
function ActivityChart({ snapshot }: { snapshot: Snapshot }) {
  const end = new Date(snapshot.as_of).getTime();
  const duration = 5 * 60 * 1000;
  const bins = Array.from({ length: 6 }, (_, i) => {
    const start = end - (6 - i) * duration;
    return { start, count: snapshot.transactions.filter((txn) => { const at = new Date(txn.timestamp).getTime(); return at > start && at <= start + duration; }).length };
  });
  const max = Math.max(1, ...bins.map((bin) => bin.count));
  const label = (time: number) => new Date(time).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: "Asia/Kolkata" });
  const total = bins.reduce((sum, bin) => sum + bin.count, 0);
  return <section className="ops-section activity-chart-panel"><div className="section-heading"><div><h2>Recent payment activity</h2><p>Last 30 minutes · five-minute intervals · IST</p></div><span className="chart-total"><strong>{total}</strong> sampled attempts</span></div>
    <div className="activity-chart" role="img" aria-label={bins.map((bin) => `${label(bin.start)} to ${label(bin.start + duration)}: ${bin.count} attempts`).join("; ")}>
      <div className="activity-bars">{bins.map((bin) => <div className="activity-column" key={bin.start}><strong>{bin.count}</strong><div className="activity-column-track"><span style={{ height: `${bin.count / max * 100}%` }} /></div><time>{label(bin.start)}</time></div>)}</div>
    </div><p className="chart-scope">Calculated from the latest {snapshot.transactions.length} transactions in this snapshot. Older records outside the snapshot are excluded.</p>
  </section>;
}
export function DashboardView() {
  const { snapshot } = useOperations();
  if (!snapshot) return <Loading />;
  const c = snapshot.counts;
  const priority = snapshot.cases.filter((item) => item.status !== "resolved").sort((a, b) => (b.priority ?? b.score * 100) - (a.priority ?? a.score * 100)).slice(0, 5);
  return <div className="workspace-view dashboard-view">
    <PageHeading title="Your operations, in focus." description="Monitor payments and move the right investigations forward."><Link href="/cases" className="primary-button">Review investigations <ArrowRight size={17} /></Link></PageHeading>
    <div className="overview-metrics">
      {[
        { label: "Payment attempts", value: c.transactions, detail: `${c.posted} posted · ${c.declined} declined`, icon: CreditCard },
        { label: "Awaiting review", value: c.pending_review, detail: `${c.investigating} investigating · ${c.escalated} escalated`, icon: Clock },
        { label: "Resolved cases", value: c.resolved, detail: `${c.confirmed_fraud} fraud · ${c.false_positives} false positives`, icon: CheckCircle },
        { label: "Active restrictions", value: c.restricted_accounts + c.restricted_cards, detail: `${c.restricted_accounts} accounts · ${c.restricted_cards} cards`, icon: ShieldCheck },
      ].map(({ label, value, detail, icon: Icon }) => <div className="overview-metric" key={label}><div><span>{label}</span><Icon size={19} aria-hidden="true" /></div><strong>{value.toLocaleString("en-IN")}</strong><small>{detail}</small></div>)}
    </div>
    {(c.failed_actions > 0 || c.pending_actions > 0) && <Link className="delivery-notice" href="/bank"><WarningCircle size={22} /><span><strong>Bank deliveries need attention</strong><small>{c.failed_actions} failed · {c.pending_actions} pending actions</small></span><span>Review deliveries <ArrowRight size={16} /></span></Link>}
    <div className="dashboard-charts"><ActivityChart snapshot={snapshot} /><ChannelChart snapshot={snapshot} /></div>
    <div className="dashboard-worklists"><section className="ops-section priority-panel"><div className="section-heading"><div><h2>Next to investigate</h2><p>Highest agent priority among the latest {snapshot.cases.length} cases</p></div><Link href="/cases" className="section-text-link">View queue <ArrowUpRight size={15} /></Link></div>
      {priority.map((item) => <Link key={item.case_id} className="focus-case-row" href={`/case?case_id=${encodeURIComponent(item.case_id)}`}><span className={`risk-score ${item.severity}`}>{(item.score * 100).toFixed(1)}</span><span className="focus-case-main"><strong>{item.account_id}<small>{channelName(item.channel)}</small></strong><span>{item.reasons[0] ?? "Review detection evidence"}</span><small className="identifier">{item.case_id}</small></span><span className="focus-case-value"><strong>{money(item.amount_minor)}</strong><small>{human(item.status)}</small></span><ArrowUpRight size={17} /></Link>)}
      {!priority.length && <Empty>The investigation queue is clear. New alerts will appear here.</Empty>}
    </section><section className="ops-section recent-events-panel"><div className="section-heading"><div><h2>Latest activity</h2><p>Payments, protection and review</p></div><Link href="/audit" className="section-text-link">Audit trail <ArrowUpRight size={15} /></Link></div><Timeline events={snapshot.events.slice(0, 4)} /></section></div>
    <div className="evidence-footnote"><ShieldCheck size={18} /><p>Synthetic local activity. Risk scores are signals, not probabilities. Real-bank performance and regulatory certification have not been established.</p><time>Snapshot {dateTime(snapshot.as_of)} IST</time></div>
  </div>;
}
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
export function LedgerView({ kind }: { kind: "cases" | "transactions" }) {
  const { snapshot, refresh } = useOperations();
  const analyst = useAnalyst();
  const [channel, setChannel] = useState("");
  const [status, setStatus] = useState("");
  const [view, setView] = useState<QueueView>("all");
  const [claiming, setClaiming] = useState<string | null>(null);
  const [reload, setReload] = useState(0);
  const [offset, setOffset] = useState(0);
  const [data, setData] = useState<{
    items: Case[] | Transaction[];
    total: number;
  } | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let cancelled = false;
    const params = new URLSearchParams({ limit: "25", offset: String(offset) });
    if (channel) params.set("channel", channel);
    if (status && kind === "cases") params.set("status", status);
    if (kind === "cases" && view !== "all") params.set("view", view);
    void opsFetch<{ items: Case[] | Transaction[]; total: number }>(
      `/${kind}?${params}`,
    )
      .then((value) => {
        if (!cancelled) {
          setData(value);
          setError("");
        }
      })
      .catch((err) => {
        if (!cancelled)
          setError(
            err instanceof Error ? err.message : "Could not load ledger.",
          );
      });
    return () => {
      cancelled = true;
    };
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
  return (
    <div className="workspace-view ledger-view">
      <PageHeading
        title={kind === "cases" ? "Investigation queue" : "Transaction ledger"}
        description={
          kind === "cases"
            ? "Review evidence, make a verdict, and track its protective action."
            : "Continuous attempted payments and the bank simulator’s actual outcomes."
        }
      />
      {kind === "transactions" && <ScenarioControls />}
      {kind === "cases" && <div className="queue-status-strip" aria-label="Filter investigation status">{[
        { value: "", label: "All investigations", count: snapshot?.counts.cases },
        { value: "new", label: "Awaiting review", count: snapshot?.counts.pending_review },
        { value: "investigating", label: "Investigating", count: snapshot?.counts.investigating },
        { value: "escalated", label: "Escalated", count: snapshot?.counts.escalated },
        { value: "resolved", label: "Resolved", count: snapshot?.counts.resolved },
      ].map((item) => <button key={item.value} aria-pressed={status === item.value} onClick={() => { setStatus(item.value); setOffset(0); }}><span>{item.label}</span><strong>{item.count?.toLocaleString("en-IN") ?? "…"}</strong></button>)}</div>}
      {kind === "cases" && <div className="queue-view-filters" role="group" aria-label="Queue view">{QUEUE_VIEWS.map((item) => <button key={item.value} aria-pressed={view === item.value} onClick={() => { setView(item.value); setOffset(0); }}>{item.label}{item.value === "awaiting_approval" && snapshot?.approvals?.length ? <b>{snapshot.approvals.length}</b> : null}</button>)}<span className="muted">Sorted by agent priority</span></div>}
      {kind === "transactions" && snapshot && <div className="ledger-context"><span><span className={`connection-dot ${snapshot.simulation_state.running ? "running" : ""}`} />Stream {snapshot.simulation_state.running ? "running" : "paused"}</span><span><strong>{snapshot.counts.posted}</strong> posted</span><span><strong>{snapshot.counts.declined}</strong> declined</span><span><strong>{snapshot.counts.pending_payments}</strong> pending</span></div>}
      <section className="ops-section ledger-panel">
        <div className="filter-bar">
          <label>
            Channel
            <select
              value={channel}
              onChange={(e) => {
                setChannel(e.target.value);
                setOffset(0);
              }}
            >
              <option value="">All channels</option>
              {CHANNELS.map((c) => (
                <option key={c} value={c}>
                  {channelName(c)}
                </option>
              ))}
            </select>
          </label>
          {kind === "cases" && (
            <label>
              Case status
              <select
                value={status}
                onChange={(e) => {
                  setStatus(e.target.value);
                  setOffset(0);
                }}
              >
                <option value="">All statuses</option>
                {["new", "investigating", "escalated", "resolved"].map((s) => (
                  <option key={s} value={s}>
                    {human(s)}
                  </option>
                ))}
              </select>
            </label>
          )}
          <p>
            {data
              ? `${data.total.toLocaleString("en-IN")} matching records`
              : "Loading records…"}
          </p>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {!data ? (
          <Loading />
        ) : kind === "cases" ? (
          <CaseTable cases={(data.items as Case[]).filter((item) => inQueueView(item, view, analyst?.username))} onClaim={(item) => { void claim(item); }} busyId={claiming} />
        ) : (
          <TransactionTable transactions={data.items as Transaction[]} />
        )}
        <div className="pagination">
          <span>
            {data?.total
              ? `${offset + 1}–${Math.min(offset + 25, data.total)} of ${data.total}`
              : "0 records"}
          </span>
          <button
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 25))}
          >
            Previous
          </button>
          <button
            disabled={!data || offset + 25 >= data.total}
            onClick={() => setOffset(offset + 25)}
          >
            Next
          </button>
        </div>
      </section>
    </div>
  );
}
export function BankView() {
  const { snapshot } = useOperations();
  if (!snapshot) return <Loading />;
  return (
    <>
      <PageHeading
        title="Bank action ledger"
        description="A request is not an enforced restriction. Confirmation comes from the separate bank simulator."
      />
      <div className="bank-status-board">
        <div className="bank-connection"><Bank size={30} aria-hidden="true" /><span><small>Simulator connection</small>
          <strong className={snapshot.bank.connected ? "good" : "bad"}>
            {snapshot.bank.connected ? "Available" : "Unavailable"}
          </strong>
        </span></div>
        <div><small>Delivery mode</small><strong>{human(snapshot.bank.mode)}</strong></div>
        <div><small>Awaiting acknowledgement</small><strong>{snapshot.counts.pending_actions}</strong></div>
        <div><small>Failed deliveries</small><strong className={snapshot.counts.failed_actions ? "bad" : ""}>{snapshot.counts.failed_actions}</strong></div>
      </div>
      <div className="bank-process-note"><ShieldCheck size={18} /><p>A protective request becomes an enforced restriction only after the bank simulator acknowledges it. Failed deliveries can be retried below.</p></div>
      {snapshot.bank.last_error && (
        <p className="form-error" role="alert">
          {snapshot.bank.last_error}
        </p>
      )}
      <section className="ops-section">
        <div className="section-heading">
          <h2>Restriction and release deliveries</h2>
          <span className="muted">
            Latest {snapshot.actions.length} actions
          </span>
        </div>
        <ActionLedger actions={snapshot.actions} />
      </section>
      <section className="ops-section">
        <div className="section-heading">
          <div>
            <h2>Simulated account positions</h2>
            <p>
              Restrictions are owned by individual cases. Releasing one case
              preserves other active restrictions. Frozen, closed and liened
              accounts are listed first.
            </p>
          </div>
        </div>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Account</th>
                <th>Status</th>
                <th>Available / balance</th>
                <th>Liens</th>
                <th>Active restrictions</th>
              </tr>
            </thead>
            <tbody>
              {[...snapshot.bank.accounts].sort((x, y) => Number(y.status !== "active" || (y.liens?.length ?? 0) > 0) - Number(x.status !== "active" || (x.liens?.length ?? 0) > 0)).map((account) => (
                <tr key={account.account_id}>
                  <td className="identifier">{account.account_id}</td>
                  <td><span className={`account-status ${account.status}`}>{account.status === "frozen" ? "Frozen" : account.status === "closed" ? "Closed" : "Active"}</span></td>
                  <td className="numeric"><strong>{money(account.available_minor)}</strong><small className="record-sub">of {money(account.balance_minor)}</small></td>
                  <td>{account.liens?.length ? <ul className="lien-list">{account.liens.map((lien) => <li key={lien.lien_id}><span className="numeric">{money(lien.amount_minor)}</span> <CaseLink id={lien.case_id} /></li>)}</ul> : <span className="muted">None</span>}</td>
                  <td>{account.active_restrictions}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {!snapshot.bank.accounts.length && (
          <Empty>No bank account positions available.</Empty>
        )}
      </section>
    </>
  );
}
export function AuditView() {
  const { snapshot } = useOperations();
  const [query, setQuery] = useState("");
  const [eventType, setEventType] = useState("");
  if (!snapshot) return <Loading />;
  const eventTypes = [...new Set(snapshot.events.map((event) => event.event_type))];
  const events = snapshot.events.filter((event) => `${event.id} ${event.event_type} ${event.message} ${event.case_id ?? ""} ${event.actor}`.toLowerCase().includes(query.toLowerCase()) && (!eventType || event.event_type === eventType));
  return (
    <>
      <PageHeading
        title="Audit trail"
        description="Persisted event history with authenticated actors and ordered event identifiers."
      />
      <section className="ops-section audit-panel">
        <div className="filter-bar">
          <label className="audit-search">
            Search recent events
            <input
              placeholder="Case, event, message or analyst"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
          <label>Event type<select value={eventType} onChange={(e) => setEventType(e.target.value)}><option value="">All event types</option>{eventTypes.map((type) => <option key={type} value={type}>{human(type)}</option>)}</select></label>
          <p aria-live="polite">{events.length} of latest {snapshot.events.length} events · IST</p>
        </div>
        {events.length ? <Timeline events={events} /> : <Empty>No events match these filters. Try a different case, actor or event type.</Empty>}
      </section>
    </>
  );
}
export function ReportsView() {
  const { snapshot } = useOperations();
  const [query, setQuery] = useState("");
  const [verdict, setVerdict] = useState("");
  if (!snapshot) return <Loading />;
  const reports = snapshot.cases.filter((item) => `${item.case_id} ${item.account_id} ${channelName(item.channel)}`.toLowerCase().includes(query.toLowerCase()) && (!verdict || item.verdict === verdict));
  const verdicts = [...new Set(snapshot.cases.map((item) => item.verdict))];
  return <div className="workspace-view reports-view"><PageHeading title="Investigation reports" description="A portable record of the evidence, decisions and bank acknowledgements."><Link href="/cases" className="secondary-button">Find an investigation <ArrowUpRight size={16} /></Link></PageHeading>
    <div className="report-library-intro"><FileText size={32} aria-hidden="true" /><div><h2>Your evidence library</h2><p>Export a case as PDF for review, Markdown for notes, or JSON for structured evidence.</p></div><span><strong>{snapshot.cases.length}</strong> recent case records</span></div>
    <section className="ops-section report-library"><div className="filter-bar"><label className="search-field">Search recent case records<span><MagnifyingGlass size={18} aria-hidden="true" /><input placeholder="Case ID, account or channel" value={query} onChange={(e) => setQuery(e.target.value)} /></span></label><label>Verdict<select value={verdict} onChange={(e) => setVerdict(e.target.value)}><option value="">All verdicts</option>{verdicts.map((value) => <option key={value} value={value}>{human(value)}</option>)}</select></label><p aria-live="polite">{reports.length} matching records</p></div>
    {reports.map((item) => <article key={item.case_id} className="library-report-row"><FileText size={23} aria-hidden="true" /><div className="library-report-main"><Link className="record-link" href={`/case?case_id=${encodeURIComponent(item.case_id)}`}>{item.case_id}</Link><p>{item.account_id} · {channelName(item.channel)}</p></div><div className="library-report-meta"><strong>{human(item.verdict)}</strong><small>Version {item.version} · {dateTime(item.updated_at)} IST</small></div><ReportButtons caseId={item.case_id} /></article>)}
    {!reports.length && <Empty>{snapshot.cases.length ? "No recent case records match your search. Try another account or clear the filters." : "Open a case before exporting an investigation report."}</Empty>}</section><p className="fine-print report-library-note">Reports capture a point in time. Later decisions do not alter a downloaded report. This library shows the latest {snapshot.cases.length} cases; use the investigation queue to find older records.</p></div>;
}
export function GuidanceView() {
  const { snapshot } = useOperations();
  const [guidance, setGuidance] = useState<Guidance | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void opsFetch<Guidance>("/guidance")
      .then((data) => {
        if (active) setGuidance(data);
      })
      .catch((err) => {
        if (active)
          setError(
            err instanceof Error ? err.message : "Guidance unavailable.",
          );
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <>
      <PageHeading
        title="Controls & guidance"
        description="Source-linked applicability and implemented controls. Alignment requires evidence, not a badge."
      />
      <section className="boundary-note">
        <strong>Scope and limitations</strong>
        <p>
          {guidance?.disclaimer ??
            "Local synthetic showcase. Formal NPCI approval, regulatory certification and real-bank validation are not claimed."}
        </p>
      </section>
      <section className="ops-section">
        <div className="section-heading">
          <div>
            <h2>Detection coverage</h2>
            <p>
              Version {snapshot?.detection.version ?? "…"}. Transparent scenario
              coverage is not real-world accuracy.
            </p>
          </div>
        </div>
        <div className="coverage-list coverage-disclosures">
          {snapshot?.detection.coverage.map((row, i) => (
            <details key={i}>
              <summary><span>{typeof row.channel === "string" ? channelName(row.channel) : `Detection coverage ${i + 1}`}</span><span>View supported signals</span></summary>
              <div>{Object.entries(row).map(([key, value]) => (
                <p key={key}>
                  <strong>{human(key)}: </strong>
                  {Array.isArray(value)
                    ? value.join(" · ")
                    : typeof value === "object"
                      ? JSON.stringify(value)
                      : String(value)}
                </p>
              ))}</div>
            </details>
          ))}
        </div>
      </section>
      {guidance?.requirements && <section className="ops-section">
        <div className="section-heading"><div>
          <h2>1930 / NCRP, RBI and NPCI requirements</h2>
          <p>Grouped by issuer. Paraphrased; unverified items are labelled.</p>
        </div></div>
        {[...new Set(guidance.requirements.map((row) => row.issuer))].map((issuer) => <div key={issuer} className="guidance-issuer">
          <h3>{issuer}</h3>
          <div className="guidance-list">{guidance.requirements!.filter((row) => row.issuer === issuer).map((row) => (
            <details key={row.source} className="guidance-disclosure">
              <summary><span><strong>{row.source}</strong><small>{row.date} · {row.status}</small></span><span>Read mapping</span></summary>
              <div className="guidance-detail">{row.url
                ? <a href={row.url} target="_blank" rel="noreferrer" className="guidance-source">Open source <ArrowUpRight size={15} /></a>
                : <p className="fine-print">No primary source verified.</p>}<dl>
                <dt>What it requires</dt><dd>{row.what_it_requires}</dd>
                <dt>How FraudLens models it</dt><dd>{row.how_fraudlens_models_it}</dd>
                <dt>Not covered</dt><dd>{row.not_covered}</dd>
              </dl></div>
            </details>))}</div>
        </div>)}
      </section>}
      <section className="ops-section">
        <div className="section-heading">
          <h2>Requirements-to-evidence matrix</h2>
        </div>
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        {guidance ? (
          <div className="guidance-list">
            {guidance.references.map((row) => (
              <details key={row.id} className="guidance-disclosure">
                <summary><span><strong>{row.title}</strong><small>{row.source_date} · {row.status}</small></span><span>Read control & evidence</span></summary>
                <div className="guidance-detail"><a href={row.source_url} target="_blank" rel="noreferrer" className="guidance-source">Open source reference <ArrowUpRight size={15} /></a><dl>
                  <dt>Applicability</dt>
                  <dd>{row.applicability}</dd>
                  <dt>Control</dt>
                  <dd>{row.control}</dd>
                  <dt>Evidence</dt>
                  <dd>{row.test_evidence.join("; ") || "Not yet verified"}</dd>
                </dl></div>
              </details>
            ))}
          </div>
        ) : (
          !error && <Loading />
        )}
      </section>
    </>
  );
}
