"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, CheckCircle, ShieldCheck } from "@phosphor-icons/react";
import {
  ACTION_LABEL,
  type ApprovalAction,
  type Brief,
  type Case,
  type CaseAction,
  type Decision,
  type TeamMember,
  OperationsError,
  ROLE_SHORT,
  assignCase,
  can,
  channelName,
  claimCase,
  dateTime,
  decideApproval,
  decideCase,
  explainError,
  getBrief,
  human,
  money,
  opsFetch,
  requestApproval,
  required,
  runCaseAction,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import {
  ActionLedger,
  Empty,
  Loading,
  PageHeading,
  ReportButtons,
  Status,
  Timeline,
  TransactionTable,
} from "./Primitives";
import { EvidenceGraph } from "./EvidenceGraph";
import { AgentBrief } from "./AgentBrief";
import { ApprovalPanel } from "./ApprovalPanel";
import { FundTrail } from "./FundTrail";
import { RoleChip } from "./RoleChip";
import { useAnalyst } from "./useAnalyst";
export function DecisionPanel({
  item,
  onUpdated,
}: {
  item: Case;
  onUpdated: (item: Case) => void;
}) {
  const { refresh, snapshot } = useOperations();
  const analyst = useAnalyst();
  const permitted = (action: CaseAction) => !analyst?.role || can(analyst.role, action);
  const [requesting, setRequesting] = useState<ApprovalAction | null>(null);
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const falsePositive = item.verdict === "false_positive";
  const resolved = item.status === "resolved";
  const canReverseFraud = resolved && item.verdict === "fraud";
  async function decide(action: Decision) {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const updated = await decideCase(
        item.case_id,
        action,
        item.version,
        notes,
      );
      onUpdated(updated);
      await refresh();
      setNotes("");
      setMessage(
        "Decision recorded. Bank-action acknowledgement determines the final resolution state.",
      );
    } catch (err) {
      setError(
        err instanceof OperationsError && err.status === 409 && !err.data.assignee
          ? "Another update changed this case. The latest record is being loaded. Review it before submitting again."
          : explainError(err, snapshot?.team, "Decision failed."),
      );
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="decision-panel">
      <div className="section-heading">
        <div>
          <h2>Analyst decision</h2>
          <p>
            Case version {item.version}. Every decision carries your identity.
          </p>
        </div>
      </div>
      {falsePositive && <p className="fine-print" role="status">{resolved
        ? "False-positive verdict is final. This case no longer has a pending release."
        : "Release is awaiting bank confirmation. Decisions are locked; retry a failed release in Bank actions."}</p>}
      {canReverseFraud && <p className="fine-print">This fraud verdict is resolved. You can reverse it with documented evidence by marking a false positive and requesting release.</p>}
      <label>
        Investigation notes
        <textarea
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          maxLength={3000}
          rows={4}
          placeholder="Explain the evidence behind your decision. Required for a fraud or false-positive verdict."
        />
      </label>
      <div className="decision-actions">
        <button
          disabled={busy || resolved || falsePositive}
          onClick={() => {
            void decide("investigate");
          }}
        >
          Start investigation
        </button>
        <button
          disabled={busy || resolved || falsePositive}
          onClick={() => {
            void decide("escalate");
          }}
        >
          Escalate
        </button>
        {permitted("confirm_fraud") ? <button
          className="danger-button"
          disabled={busy || resolved || falsePositive || !notes.trim()}
          onClick={() => {
            void decide("confirm_fraud");
          }}
        >
          Confirm fraud
        </button> : <button
          disabled={busy || resolved || falsePositive || Boolean(item.pending_approval)}
          onClick={() => setRequesting("confirm_fraud")}
        >
          Request approval to confirm fraud
        </button>}
        {permitted("false_positive") ? <button
          className="primary-button"
          disabled={busy || falsePositive || (resolved && !canReverseFraud) || !notes.trim()}
          onClick={() => {
            void decide("false_positive");
          }}
        >
          Mark false positive & release
        </button> : <button
          disabled={busy || falsePositive || (resolved && !canReverseFraud) || Boolean(item.pending_approval)}
          onClick={() => setRequesting("false_positive")}
        >
          Request approval to mark false positive
        </button>}
      </div>
      {requesting && <ApprovalPanel mode="request" action={requesting} requiredRole={required(requesting)} busy={busy}
        onCancel={() => setRequesting(null)}
        onSubmit={(text) => {
          setBusy(true);
          setError("");
          void requestApproval(item.case_id, requesting, item.version, text, item.default_target_account_id)
            .then((updated) => { onUpdated(updated); setRequesting(null); setMessage(`Approval requested from ${ROLE_SHORT[required(requesting)]}.`); })
            .catch((err) => setError(explainError(err, snapshot?.team)))
            .finally(() => { setBusy(false); void refresh().catch(() => {}); });
        }} />}
      <p className="fine-print">
        A false-positive verdict requests release of this case’s restriction. It
        cannot remove restrictions owned by another case.
      </p>
      {busy && <p role="status">Recording decision…</p>}
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {message && (
        <p className="success-message" role="status">
          {message}
        </p>
      )}
    </section>
  );
}
const NEEDS_RATIONALE: CaseAction[] = ["confirm_fraud", "false_positive", "close_account", "file_ncrp_report"];
const nameOf = (team: TeamMember[] | undefined, username: string) =>
  team?.find((m) => m.username === username)?.display_name ?? username;
function OwnerRow({ item, team, onChanged }: { item: Case; team?: TeamMember[]; onChanged: (item: Case) => void }) {
  const analyst = useAnalyst();
  const { refresh } = useOperations();
  const [target, setTarget] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const owner = item.assignee ? nameOf(team, item.assignee) : null;
  const handled = (item.handled_by ?? []).map((u) => nameOf(team, u));
  async function run(task: () => Promise<Case>) {
    setBusy(true);
    setError("");
    try {
      onChanged(await task());
    } catch (err) {
      setError(explainError(err, team));
    } finally {
      setBusy(false);
      await refresh().catch(() => {});
    }
  }
  return <div className="owner-row">
    <p>{owner ? `Assigned to ${owner}` : "Unassigned"}{handled.length > 0 && ` · handled by ${handled.join(", ")}`}</p>
    {!item.assignee && item.status !== "resolved" && <button disabled={busy} onClick={() => { void run(() => claimCase(item.case_id, item.version)); }}>Claim</button>}
    {can(analyst?.role, "assign") && team && <span className="reassign">
      <label className="sr-only" htmlFor="reassign-target">Reassign to</label>
      <select id="reassign-target" value={target} onChange={(e) => setTarget(e.target.value)}>
        <option value="">Reassign to…</option>
        {team.filter((m) => m.username !== item.assignee).map((m) => <option key={m.username} value={m.username}>{m.display_name} · {m.role_label}</option>)}
      </select>
      <button disabled={busy || !target} onClick={() => { void run(() => assignCase(item.case_id, target, item.version)); }}>Reassign</button>
    </span>}
    {error && <p className="form-error" role="alert">{error}{error.endsWith("already claimed this case.") && <button onClick={() => { setError(""); void refresh().catch(() => {}); }}>Refresh</button>}</p>}
  </div>;
}
export default function CaseWorkspace({ caseId }: { caseId: string }) {
  const { snapshot, refresh, setCurrentCase } = useOperations();
  const analyst = useAnalyst();
  const [item, setItem] = useState<Case | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [requesting, setRequesting] = useState<{ action: ApprovalAction; target: string | null } | null>(null);
  const [rationale, setRationale] = useState("");
  useEffect(() => {
    if (!caseId) return;
    setCurrentCase(caseId);
    return () => setCurrentCase(null);
  }, [caseId, setCurrentCase]);
  useEffect(() => {
    if (!caseId) return;
    let active = true;
    void opsFetch<Case>(`/cases/${encodeURIComponent(caseId)}`)
      .then((value) => {
        if (active) {
          setItem(value);
          setError("");
        }
      })
      .catch((err) => {
        if (active)
          setError(err instanceof Error ? err.message : "Case unavailable.");
      });
    return () => {
      active = false;
    };
  }, [caseId, snapshot?.cursor]);
  const version = item?.version;
  useEffect(() => {
    if (!caseId || version === undefined) return;
    let active = true;
    void getBrief(caseId).then((value) => { if (active) setBrief(value); }).catch(() => {});
    return () => { active = false; };
  }, [caseId, version]);
  if (!caseId)
    return (
      <>
        <PageHeading
          title="Investigation workspace"
          description="Choose a case to inspect evidence and record a decision."
        />
        <Empty>
          <Link href="/cases">Open the investigation queue →</Link>
        </Empty>
      </>
    );
  if (error && !item)
    return (
      <>
        <PageHeading title="Case unavailable" description={error} />
        <Link href="/cases">Return to investigations →</Link>
      </>
    );
  if (!item) return <Loading />;
  const current = item;
  const shownBrief = brief ?? item.brief ?? null;
  const team = snapshot?.team;
  const approval = item.pending_approval;
  const canDecideApproval = Boolean(approval && analyst && approval.requested_by !== analyst.username && can(analyst.role, approval.action));
  const latestAction = [...item.actions]
    .sort((a, b) => a.created_at.localeCompare(b.created_at))
    .at(-1);
  const closedTargets = new Set(item.actions.filter((a) => a.operation === "close" && a.status !== "superseded").map((a) => a.target_id));
  async function perform(task: () => Promise<Case>, done: string) {
    setBusy(true);
    setActionError("");
    setActionMessage("");
    try {
      setItem(await task());
      setActionMessage(done);
      setRationale("");
    } catch (err) {
      setActionError(explainError(err, team));
    } finally {
      setBusy(false);
      await refresh().catch(() => {});
    }
  }
  function runRecommended(action: CaseAction, target: string | null = shownBrief?.target_account_id ?? null) {
    if (NEEDS_RATIONALE.includes(action) && !rationale.trim()) {
      setActionError("Add a rationale before recording this action.");
      return;
    }
    void perform(() => runCaseAction(current.case_id, action, current.version, rationale, {
      amount_minor: action === "place_lien" ? shownBrief?.amount_minor : undefined, target_account_id: target,
    }), `${ACTION_LABEL[action]} recorded. The bank's acknowledgement decides the outcome.`);
  }
  function ask(action: CaseAction, target: string | null = shownBrief?.target_account_id ?? null) {
    if (action === "investigate" || action === "escalate" || action === "place_lien") return;
    setRequesting({ action, target });
  }
  return (
    <>
      <div className="case-back">
          <Link href="/cases"><ArrowLeft size={12}/>Investigation queue</Link>
        <span>Updated {dateTime(item.updated_at)} IST</span>
      </div>
      <PageHeading
        title={`${shownBrief?.typology ?? channelName(item.channel)} · ${item.case_id}`}
        description={`${channelName(item.channel)} · ${item.account_id} · ${money(item.amount_minor)}${item.complaint ? ` · ${item.complaint.complaint_id}` : ""}`}
      >
        <ReportButtons caseId={item.case_id} />
      </PageHeading>
      <div className="case-meta-row">
        <span className="priority-pill" title={item.priority_reason}>Priority <strong>{item.priority ?? "—"}</strong>{item.priority_reason && <small>{item.priority_reason}</small>}</span>
        {shownBrief && <span className="required-role">Needs <RoleChip role={shownBrief.required_role} /></span>}
      </div>
      <OwnerRow item={item} team={team} onChanged={setItem} />
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {approval && (canDecideApproval
        ? <ApprovalPanel mode="decide" approval={approval} requesterName={nameOf(team, approval.requested_by)} busy={busy}
            onDecide={(approve, notes) => { void perform(() => decideApproval(current.case_id, approve, notes), approve ? "Approved. The action now runs under your name." : "Request rejected and recorded."); }} />
        : <p className="approval-waiting" role="status">Awaiting approval from {ROLE_SHORT[approval.required_role]}: {ACTION_LABEL[approval.action]} (requested by {nameOf(team, approval.requested_by)})</p>)}
      <div className="case-state-strip">
        <div>
          <span>Investigation</span>
          <Status value={item.status} />
        </div>
        <div>
          <span>Analyst verdict</span>
          <Status value={item.verdict} />
        </div>
        <div>
          <span>Detection score</span>
          <strong className={`risk-score ${item.severity}`}>
            {(item.score * 100).toFixed(1)} / 100
          </strong>
        </div>
        <div>
          <span>Protection</span>
          <strong>
            {latestAction
              ? `${human(latestAction.operation)} ${latestAction.status}`
              : "No action recorded"}
          </strong>
        </div>
      </div>
      <div className="case-columns">
        <div>
          {shownBrief && <AgentBrief brief={shownBrief} role={analyst?.role} busy={busy} onRun={(action) => runRecommended(action)} onRequest={(action) => ask(action)} />}
          {shownBrief && NEEDS_RATIONALE.includes(shownBrief.recommended_action) && can(analyst?.role, shownBrief.recommended_action) && <label className="brief-rationale">Rationale for {ACTION_LABEL[shownBrief.recommended_action].toLowerCase()}
            <textarea rows={2} maxLength={3000} value={rationale} onChange={(e) => setRationale(e.target.value)} placeholder="Required. Recorded in the audit trail with your name." /></label>}
          {requesting && <ApprovalPanel mode="request" action={requesting.action} requiredRole={required(requesting.action)} busy={busy}
            onCancel={() => setRequesting(null)}
            onSubmit={(notes) => { const r = requesting; void perform(() => requestApproval(current.case_id, r.action, current.version, notes, r.target), `Approval requested from ${ROLE_SHORT[required(r.action)]}.`).then(() => setRequesting(null)); }} />}
          {actionError && <p className="form-error" role="alert">{actionError}</p>}
          {actionMessage && <p className="success-message" role="status">{actionMessage}</p>}
          {item.case_type === "complaint" && item.complaint && item.trace && <FundTrail victimAccountId={item.complaint.victim_account_id} reportedMinor={item.amount_minor} trace={item.trace} transactions={item.related_transactions}
            renderAction={item.verdict === "fraud" ? (hop) => closedTargets.has(hop.account_id)
              ? <span className="fine-print">Closure requested</span>
              : can(analyst?.role, "close_account")
                ? <button className="danger-button" disabled={busy || !rationale.trim()} title={rationale.trim() ? undefined : "Add a rationale above first"} onClick={() => runRecommended("close_account", hop.account_id)}>Close account …{hop.account_id.slice(-4)}</button>
                : <button disabled={busy || Boolean(approval)} onClick={() => ask("close_account", hop.account_id)}>Request closure of …{hop.account_id.slice(-4)}</button>
              : undefined} />}
          <section className="ops-section">
            <div className="section-heading">
              <div>
                <h2>Why this payment was flagged</h2>
                <p>Detection reasons and individual signal contributions.</p>
              </div>
            </div>
            <ul className="reason-list">
              {item.reasons.map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
            <div className="signal-list">
              {item.signals.map((signal, i) => (
                <div key={`${signal.name}-${i}`}>
                  <div>
                    <strong>{human(signal.name)}</strong>
                    <span className="numeric">
                      {(signal.score * 100).toFixed(1)}
                    </span>
                  </div>
                  <meter
                    min="0"
                    max="100"
                    value={signal.score * 100}
                    aria-label={`${signal.name} score`}
                  />
                  {signal.reasons.length > 0 && (
                    <p>{signal.reasons.join(" · ")}</p>
                  )}
                </div>
              ))}
            </div>
          </section>
          <section className="recommendation">
            <strong>
              {item.status === "resolved" ? <CheckCircle size={18} weight="duotone"/> : <ShieldCheck size={18} weight="duotone"/>}
              {item.verdict === "false_positive"
                ? item.status === "resolved" ? "False positive resolved" : "Awaiting release acknowledgement"
                : item.verdict === "fraud"
                  ? "Fraud confirmed by analyst"
                  : "Review the detected pattern"}
            </strong>
            <p>
              {item.verdict === "unreviewed"
                ? "Automated detection is a signal. Investigate the triggering evidence and account history before recording a verdict."
                : item.notes ||
                  "Check delivery status and the case timeline for the latest outcome."}
            </p>
          </section>
          <DecisionPanel key={item.case_id} item={item} onUpdated={setItem} />
          <section className="ops-section">
            <div className="section-heading">
              <h2>Bank actions</h2>
            </div>
            <ActionLedger actions={item.actions} />
          </section>
          <section className="ops-section">
            <div className="section-heading">
              <h2>Related payment attempts</h2>
            </div>
            <TransactionTable transactions={item.related_transactions} />
          </section>
        </div>
        <div>
          <section className="ops-section">
            <div className="section-heading">
              <h2>Evidence connections</h2>
            </div>
            <EvidenceGraph cases={[item]} />
            <p className="fine-print graph-caption">
              Connections show shared account, beneficiary or instrument
              identifiers present in the case evidence.
            </p>
          </section>
          <section className="ops-section">
            <div className="section-heading">
              <div>
                <h2>Incident timeline</h2>
                <p>Payment → protection → analyst review</p>
              </div>
            </div>
            <Timeline events={[...item.timeline].sort((a, b) => a.id - b.id)} />
          </section>
        </div>
      </div>
    </>
  );
}
