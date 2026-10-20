"use client";
import { useState } from "react";
import { ACTION_LABEL, ROLE_SHORT, type CaseAction, type PendingApproval, type Role } from "@/lib/operations";
type Props =
  | {
      mode: "decide";
      approval: PendingApproval;
      requesterName: string;
      busy?: boolean;
      onDecide: (approve: boolean, notes: string) => void;
    }
  | {
      mode: "request";
      action: CaseAction;
      requiredRole: Role;
      busy?: boolean;
      onSubmit: (notes: string) => void;
      onCancel: () => void;
    };
export function ApprovalPanel(props: Props) {
  const [notes, setNotes] = useState("");
  const empty = !notes.trim();
  if (props.mode === "decide") {
    const { approval, requesterName, busy, onDecide } = props;
    return (
      <section className="approval-panel" aria-label="Approval request">
        <p>
          <strong>
            {requesterName} requests: {ACTION_LABEL[approval.action]} — {approval.notes}
          </strong>
        </p>
        {approval.target_account_id && (
          <p className="fine-print">Target account {approval.target_account_id}</p>
        )}
        <label>
          Decision notes
          <textarea
            rows={2}
            maxLength={3000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Required to reject. Optional when approving."
          />
        </label>
        <div className="decision-actions">
          <button className="primary-button" disabled={busy} onClick={() => onDecide(true, notes)}>
            Approve
          </button>
          <button className="danger-button" disabled={busy || empty} onClick={() => onDecide(false, notes)}>
            Reject
          </button>
        </div>
      </section>
    );
  }
  const { action, requiredRole, busy, onSubmit, onCancel } = props;
  return (
    <section className="approval-panel" aria-label="Request approval">
      <p>
        <strong>Request approval: {ACTION_LABEL[action]}</strong>
      </p>
      <label>
        Why should this happen?
        <textarea
          rows={3}
          maxLength={3000}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Summarise the evidence for the approver. Required."
        />
      </label>
      <div className="decision-actions">
        <button className="primary-button" disabled={busy || empty} onClick={() => onSubmit(notes)}>
          Send request to {ROLE_SHORT[requiredRole]}
        </button>
        <button disabled={busy} onClick={onCancel}>
          Cancel
        </button>
      </div>
    </section>
  );
}
