import type { CaseAction, Role, Snapshot } from "./ops-types";

export const ROLE_RANK: Record<Role, number> = {
  l1_analyst: 1,
  l2_analyst: 2,
  supervisor: 3,
};
export const ROLE_LABEL: Record<Role, string> = {
  l1_analyst: "L1 Analyst",
  l2_analyst: "L2 Senior Analyst",
  supervisor: "Fraud Supervisor",
};
export const ROLE_SHORT: Record<Role, string> = {
  l1_analyst: "L1",
  l2_analyst: "L2",
  supervisor: "Supervisor",
};
// Mirrors fraudlens/core/auth/roles.py ACTION_MIN_ROLE. The API enforces it;
// the console only uses it to offer "Request approval" instead of a 403.
// tests/test_role_parity.py fails if the two tables differ.
export const ACTION_MIN_ROLE: Record<string, Role> = {
  claim: "l1_analyst",
  investigate: "l1_analyst",
  escalate: "l1_analyst",
  place_lien: "l1_analyst",
  release_lien: "l2_analyst",
  restrict: "l2_analyst",
  confirm_fraud: "l2_analyst",
  false_positive: "l2_analyst",
  assign: "l2_analyst",
  approve_l2: "l2_analyst",
  close_account: "supervisor",
  file_ncrp_report: "supervisor",
  approve_supervisor: "supervisor",
  agent_settings: "supervisor",
};
export const required = (action: string): Role => ACTION_MIN_ROLE[action] ?? "supervisor";
export function can(role: Role | undefined, action: string) {
  const needed = ACTION_MIN_ROLE[action];
  return Boolean(role && needed && ROLE_RANK[role] >= ROLE_RANK[needed]);
}
/** Pending approvals this analyst may decide: role permits it and it is not their own request. */
export function decidableApprovals(
  snapshot: Snapshot | null,
  analyst: { username: string; role: Role } | null,
) {
  return (snapshot?.approvals ?? []).filter(
    (a) => analyst && a.requested_by !== analyst.username && can(analyst.role, a.action),
  );
}
export const ACTION_LABEL: Record<CaseAction, string> = {
  investigate: "Start investigation",
  escalate: "Escalate",
  confirm_fraud: "Confirm fraud",
  false_positive: "Mark false positive",
  restrict: "Restrict account",
  place_lien: "Place lien",
  release_lien: "Release lien",
  close_account: "Close account",
  file_ncrp_report: "Record NCRP report",
};
