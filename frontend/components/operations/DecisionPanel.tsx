"use client";
import { useState } from "react";
import {
  type ApprovalAction,
  type Case,
  type CaseAction,
  type Decision,
  OperationsError,
  ROLE_SHORT,
  can,
  decideCase,
  explainError,
  requestApproval,
  required,
} from "@/lib/operations";
import { useOperations } from "./OperationsProvider";
import { ApprovalPanel } from "./ApprovalPanel";
import { useAnalyst } from "./useAnalyst";

const STALE_VERSION =
  "Another update changed this case. The latest record is being loaded. Review it before submitting again.";

export function DecisionPanel({ item, onUpdated }: { item: Case; onUpdated: (item: Case) => void }) {
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
  const locked = busy || resolved || falsePositive;
  const releaseLocked = busy || falsePositive || (resolved && !canReverseFraud);

  async function decide(action: Decision) {
    setError("");
    setMessage("");
    setBusy(true);
    try {
      const updated = await decideCase(item.case_id, action, item.version, notes);
      onUpdated(updated);
      await refresh();
      setNotes("");
      setMessage("Decision recorded. Bank-action acknowledgement determines the final resolution state.");
    } catch (err) {
      const stale = err instanceof OperationsError && err.status === 409 && !err.data.assignee;
      setError(stale ? STALE_VERSION : explainError(err, snapshot?.team, "Decision failed."));
      await refresh().catch(() => {});
    } finally {
      setBusy(false);
    }
  }

  function submitRequest(action: ApprovalAction, text: string) {
    setBusy(true);
    setError("");
    void requestApproval(item.case_id, action, item.version, text, item.default_target_account_id)
      .then((updated) => {
        onUpdated(updated);
        setRequesting(null);
        setMessage(`Approval requested from ${ROLE_SHORT[required(action)]}.`);
      })
      .catch((err) => setError(explainError(err, snapshot?.team)))
      .finally(() => {
        setBusy(false);
        void refresh().catch(() => {});
      });
  }

  return (
    <section className="decision-panel">
      <div className="section-heading">
        <div>
          <h2>Analyst decision</h2>
          <p>Case version {item.version}. Every decision carries your identity.</p>
        </div>
      </div>
      {falsePositive && (
        <p className="fine-print" role="status">
          {resolved
            ? "False-positive verdict is final. This case no longer has a pending release."
            : "Release is awaiting bank confirmation. Decisions are locked; retry a failed release in Bank actions."}
        </p>
      )}
      {canReverseFraud && (
        <p className="fine-print">
          This fraud verdict is resolved. You can reverse it with documented evidence by marking a false
          positive and requesting release.
        </p>
      )}
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
          disabled={locked}
          onClick={() => {
            void decide("investigate");
          }}
        >
          Start investigation
        </button>
        <button
          disabled={locked}
          onClick={() => {
            void decide("escalate");
          }}
        >
          Escalate
        </button>
        {permitted("confirm_fraud") ? (
          <button
            className="danger-button"
            disabled={locked || !notes.trim()}
            onClick={() => {
              void decide("confirm_fraud");
            }}
          >
            Confirm fraud
          </button>
        ) : (
          <button
            disabled={locked || Boolean(item.pending_approval)}
            onClick={() => setRequesting("confirm_fraud")}
          >
            Request approval to confirm fraud
          </button>
        )}
        {permitted("false_positive") ? (
          <button
            className="primary-button"
            disabled={releaseLocked || !notes.trim()}
            onClick={() => {
              void decide("false_positive");
            }}
          >
            Mark false positive & release
          </button>
        ) : (
          <button
            disabled={releaseLocked || Boolean(item.pending_approval)}
            onClick={() => setRequesting("false_positive")}
          >
            Request approval to mark false positive
          </button>
        )}
      </div>
      {requesting && (
        <ApprovalPanel
          mode="request"
          action={requesting}
          requiredRole={required(requesting)}
          busy={busy}
          onCancel={() => setRequesting(null)}
          onSubmit={(text) => submitRequest(requesting, text)}
        />
      )}
      <p className="fine-print">
        A false-positive verdict requests release of this case’s restriction. It cannot remove restrictions
        owned by another case.
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
