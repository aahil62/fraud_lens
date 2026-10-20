"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import {
  ACTION_LABEL,
  type ApprovalAction,
  type Brief,
  type Case,
  type CaseAction,
  type TraceHop,
  ROLE_SHORT,
  can,
  decideApproval,
  explainError,
  getBrief,
  opsFetch,
  requestApproval,
  required,
  runCaseAction,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import { ActionLedger, Empty, Loading, PageHeading, Timeline, TransactionTable } from "./Primitives";
import { EvidenceGraph } from "./EvidenceGraph";
import { AgentBrief } from "./AgentBrief";
import { ApprovalPanel } from "./ApprovalPanel";
import { CaseHeader, StateStrip, nameOf } from "./CaseHeader";
import { FlaggedReasons, VerdictNote } from "./CaseEvidence";
import { DecisionPanel } from "./DecisionPanel";
import { FundTrail } from "./FundTrail";
import { useAnalyst } from "./useAnalyst";

export { DecisionPanel } from "./DecisionPanel";

const NEEDS_RATIONALE: CaseAction[] = [
  "confirm_fraud",
  "false_positive",
  "close_account",
  "file_ncrp_report",
];

/** Loads the case and its agent brief, refreshing both when the snapshot moves on. */
function useCase(caseId: string, cursor: number | undefined) {
  const [item, setItem] = useState<Case | null>(null);
  const [brief, setBrief] = useState<Brief | null>(null);
  const [error, setError] = useState("");
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
        if (active) setError(err instanceof Error ? err.message : "Case unavailable.");
      });
    return () => {
      active = false;
    };
  }, [caseId, cursor]);
  const version = item?.version;
  useEffect(() => {
    if (!caseId || version === undefined) return;
    let active = true;
    void getBrief(caseId)
      .then((value) => {
        if (active) setBrief(value);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, [caseId, version]);
  return { item, setItem, brief, error };
}

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
                ).then(() => setRequesting(null));
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
        <div>
          <section className="ops-section">
            <div className="section-heading">
              <h2>Evidence connections</h2>
            </div>
            <EvidenceGraph cases={[item]} />
            <p className="fine-print graph-caption">
              Connections show shared account, beneficiary or instrument identifiers present in the case
              evidence.
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
