"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ACTION_LABEL,
  type ApprovalAction,
  type Case,
  type CaseAction,
  type TraceHop,
  ROLE_SHORT,
  can,
  decideApproval,
  explainError,
  requestApproval,
  required,
  runCaseAction,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import { ActionLedger } from "./ActionLedger";
import { Empty, Loading, PageHeading } from "./Primitives";
import { TransactionTable } from "./Records";
import { AgentBrief } from "./AgentBrief";
import { ApprovalPanel } from "./ApprovalPanel";
import { CaseHeader, StateStrip, nameOf } from "./CaseHeader";
import { CaseConnections, FlaggedReasons, VerdictNote } from "./CaseEvidence";
import { DecisionPanel } from "./DecisionPanel";
import { FundTrail } from "./FundTrail";
import { useAnalyst } from "./useAnalyst";
import { useCase } from "./useCase";

export { DecisionPanel } from "./DecisionPanel";

const NEEDS_RATIONALE: CaseAction[] = [
  "confirm_fraud",
  "false_positive",
  "close_account",
  "file_ncrp_report",
];

export default function CaseWorkspace({ caseId }: { caseId: string }) {
  const { snapshot, refresh, setCurrentCase } = useOperations();
  const analyst = useAnalyst();
  const { item, setItem, brief, error } = useCase(caseId, snapshot?.cursor);
  const [actionError, setActionError] = useState("");
  const [actionMessage, setActionMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [requesting, setRequesting] = useState<{ action: ApprovalAction; target: string | null } | null>(
    null,
  );
  const [rationale, setRationale] = useState("");

  useEffect(() => {
    if (!caseId) return;
    setCurrentCase(caseId);
    return () => setCurrentCase(null);
  }, [caseId, setCurrentCase]);

  if (!caseId) {
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
  }
  if (error && !item) {
    return (
      <>
        <PageHeading title="Case unavailable" description={error} />
        <Link href="/cases">Return to investigations →</Link>
      </>
    );
  }
  if (!item) return <Loading />;

  const current = item;
  const shownBrief = brief ?? item.brief ?? null;
  const team = snapshot?.team;
  const approval = item.pending_approval;
  const canDecideApproval = Boolean(
    approval && analyst && approval.requested_by !== analyst.username && can(analyst.role, approval.action),
  );
  const closedTargets = new Set(
    item.actions.filter((a) => a.operation === "close" && a.status !== "superseded").map((a) => a.target_id),
  );

  /** Runs a case action; resolves true when it succeeded. */
  async function perform(task: () => Promise<Case>, done: string) {
    setBusy(true);
    setActionError("");
    setActionMessage("");
    try {
      setItem(await task());
      setActionMessage(done);
      setRationale("");
      return true;
    } catch (err) {
      setActionError(explainError(err, team));
      return false;
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
    const options = {
      amount_minor: action === "place_lien" ? shownBrief?.amount_minor : undefined,
      target_account_id: target,
    };
    void perform(
      () => runCaseAction(current.case_id, action, current.version, rationale, options),
      `${ACTION_LABEL[action]} recorded. The bank's acknowledgement decides the outcome.`,
    );
  }

  function ask(action: CaseAction, target: string | null = shownBrief?.target_account_id ?? null) {
    if (action === "investigate" || action === "escalate" || action === "place_lien") return;
    setRequesting({ action, target });
  }

  /** "Close account" on a traced mule hop, only after a confirmed-fraud verdict. */
  function closeHopAction(hop: TraceHop) {
    if (closedTargets.has(hop.account_id)) return <span className="fine-print">Closure requested</span>;
    const suffix = hop.account_id.slice(-4);
    if (can(analyst?.role, "close_account")) {
      return (
        <button
          className="danger-button"
          disabled={busy || !rationale.trim()}
          title={rationale.trim() ? undefined : "Add a rationale above first"}
          onClick={() => runRecommended("close_account", hop.account_id)}
        >
          Close account …{suffix}
        </button>
      );
    }
    return (
      <button disabled={busy || Boolean(approval)} onClick={() => ask("close_account", hop.account_id)}>
        Request closure of …{suffix}
      </button>
    );
  }

  const showRationale =
    shownBrief &&
    NEEDS_RATIONALE.includes(shownBrief.recommended_action) &&
    can(analyst?.role, shownBrief.recommended_action);

  return (
    <>
      <CaseHeader item={item} brief={shownBrief} team={team} onChanged={setItem} />
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
      {approval &&
        (canDecideApproval ? (
          <ApprovalPanel
            mode="decide"
            approval={approval}
            requesterName={nameOf(team, approval.requested_by)}
            busy={busy}
            onDecide={(approve, notes) => {
              void perform(
                () => decideApproval(current.case_id, approve, notes),
                approve ? "Approved. The action now runs under your name." : "Request rejected and recorded.",
              );
            }}
          />
        ) : (
          <p className="approval-waiting" role="status">
            Awaiting approval from {ROLE_SHORT[approval.required_role]}: {ACTION_LABEL[approval.action]}{" "}
            (requested by {nameOf(team, approval.requested_by)})
          </p>
        ))}
      <StateStrip item={item} />
      <div className="case-columns">
        <div>
          {shownBrief && (
            <AgentBrief
              brief={shownBrief}
              role={analyst?.role}
              busy={busy}
              onRun={(action) => runRecommended(action)}
              onRequest={(action) => ask(action)}
            />
          )}
          {showRationale && (
            <label className="brief-rationale">
              Rationale for {ACTION_LABEL[shownBrief.recommended_action].toLowerCase()}
              <textarea
                rows={2}
                maxLength={3000}
                value={rationale}
                onChange={(e) => setRationale(e.target.value)}
                placeholder="Required. Recorded in the audit trail with your name."
              />
            </label>
          )}
          {requesting && (
            <ApprovalPanel
              mode="request"
              action={requesting.action}
              requiredRole={required(requesting.action)}
              busy={busy}
              onCancel={() => setRequesting(null)}
              onSubmit={(notes) => {
                const request = requesting;
                void perform(
                  () =>
                    requestApproval(current.case_id, request.action, current.version, notes, request.target),
                  `Approval requested from ${ROLE_SHORT[required(request.action)]}.`,
                ).then((succeeded) => succeeded && setRequesting(null));
              }}
            />
          )}
          {actionError && (
            <p className="form-error" role="alert">
              {actionError}
            </p>
          )}
          {actionMessage && (
            <p className="success-message" role="status">
              {actionMessage}
            </p>
          )}
          {item.case_type === "complaint" && item.complaint && item.trace && (
            <FundTrail
              victimAccountId={item.complaint.victim_account_id}
              reportedMinor={item.amount_minor}
              trace={item.trace}
              transactions={item.related_transactions}
              renderAction={item.verdict === "fraud" ? closeHopAction : undefined}
            />
          )}
          <FlaggedReasons item={item} />
          <VerdictNote item={item} />
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
        <CaseConnections item={item} />
      </div>
    </>
  );
}
