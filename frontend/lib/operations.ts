import { getToken } from "./auth";

export const OPS_BASE =
  (process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8001") + "/ops";
export const CHANNELS = ["upi", "net_banking", "card", "atm"] as const;
export type Channel = (typeof CHANNELS)[number];
export const channelName = (channel: string) =>
  ({ upi: "UPI", net_banking: "Net banking", card: "Cards", atm: "ATMs" })[
    channel
  ] ?? channel;
export type Transaction = {
  txn_id: string;
  account_id: string;
  channel: Channel;
  amount_minor: number;
  timestamp: string;
  instrument_id: string | null;
  beneficiary_id: string | null;
  merchant_id: string;
  device_id: string;
  ip_address: string;
  location: string;
  new_device: boolean;
  new_beneficiary: boolean;
  failed_auth_attempts: number;
  score: number;
  payment_status: string;
  bank_reason: string | null;
  case_id: string | null;
};
export type BankAction = {
  action_id: string;
  case_id: string;
  operation: "restrict" | "release" | "lien" | "lien_release" | "close";
  amount_minor?: number;
  target_type: "account" | "card";
  target_id: string;
  status: "pending" | "confirmed" | "failed" | "superseded";
  attempts: number;
  bank_reference: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
};
export type AuditEvent = {
  id: number;
  event_type: string;
  case_id: string | null;
  txn_id: string | null;
  actor: string;
  message: string;
  occurred_at: string;
  metadata: Record<string, unknown>;
};
export type Case = {
  case_id: string;
  txn_id: string;
  account_id: string;
  channel: Channel;
  amount_minor: number;
  score: number;
  severity: string;
  status: string;
  verdict: string;
  version: number;
  created_at: string;
  updated_at: string;
  assigned_to: string | null;
  assignee?: string | null;
  assigned_at?: string | null;
  pending_approval?: PendingApproval | null;
  handled_by?: string[];
  priority?: number;
  priority_reason?: string;
  case_type?: "detector" | "complaint";
  complaint?: {
    complaint_id: string;
    source: "1930_helpline" | "ncrp_portal" | "branch";
    victim_account_id: string;
    reported_txn_id: string;
    reported_at: string;
  };
  trace?: TraceHop[];
  traced_total_minor?: number;
  held_total_minor?: number;
  funds_moved_total_minor?: number;
  default_target_account_id?: string | null;
  brief?: Brief;
  notes: string;
  signals: { name: string; score: number; reasons: string[] }[];
  reasons: string[];
  related_transactions: Transaction[];
  related_accounts: string[];
  actions: BankAction[];
  timeline: AuditEvent[];
};
export type Counts = {
  transactions: number;
  pending_payments: number;
  posted: number;
  declined: number;
  cases: number;
  pending_review: number;
  investigating: number;
  escalated: number;
  resolved: number;
  confirmed_fraud: number;
  false_positives: number;
  restricted_accounts: number;
  restricted_cards: number;
  pending_actions: number;
  failed_actions: number;
};
export type Snapshot = {
  cursor: number;
  as_of: string;
  simulation: true;
  counts: Counts;
  channels: {
    channel: Channel;
    transactions: number;
    cases: number;
    pending_review: number;
    confirmed_fraud: number;
    resolved: number;
    declined: number;
  }[];
  transactions: Transaction[];
  cases: Case[];
  actions: BankAction[];
  events: AuditEvent[];
  bank: {
    connected: boolean;
    mode: string;
    accounts: {
      account_id: string;
      balance_minor: number;
      available_minor: number;
      status: "active" | "frozen" | "closed";
      liens: { lien_id: string; case_id: string; amount_minor: number }[];
      restricted: boolean;
      active_restrictions: number;
    }[];
    last_error: string | null;
  };
  team?: TeamMember[];
  approvals?: (PendingApproval & { case_id: string })[];
  agent?: AgentState;
  simulation_state: { running: boolean; interval_seconds: number };
  detection: { version: string; coverage: Record<string, unknown>[] };
};
export type Decision =
  "investigate" | "escalate" | "confirm_fraud" | "false_positive";
export type Role = "l1_analyst" | "l2_analyst" | "supervisor";
export type CaseAction =
  | Decision
  | "restrict"
  | "place_lien"
  | "release_lien"
  | "close_account"
  | "file_ncrp_report";
export type ApprovalAction = Exclude<
  CaseAction,
  "investigate" | "escalate" | "place_lien"
>;
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
export const required = (action: string): Role =>
  ACTION_MIN_ROLE[action] ?? "supervisor";
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
    (a) =>
      analyst &&
      a.requested_by !== analyst.username &&
      can(analyst.role, a.action),
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
export type PendingApproval = {
  approval_id: string;
  action: ApprovalAction;
  requested_by: string;
  required_role: Role;
  notes: string;
  requested_at: string;
  target_account_id?: string | null;
};
export type TraceHop = {
  hop: number;
  account_id: string;
  inbound_txn_ids: string[];
  traced_minor: number;
  available_minor: number;
  lien_minor: number;
  moved_minor?: number;
  lien_status?: string;
  outcome:
    | "held"
    | "partially_recovered"
    | "funds_moved"
    | "account_closed"
    | "pending"
    | "released";
};
export type Brief = {
  typology: string;
  summary: string;
  evidence: string[];
  recommended_action: CaseAction;
  target_account_id: string | null;
  amount_minor: number | null;
  required_role: Role;
  required_role_label: string;
  confidence: "low" | "medium" | "high";
  next_steps: string[];
  ncrp_narrative: string;
  generated_by: "template" | "llm";
};
export type TeamMember = {
  username: string;
  display_name: string;
  role: Role;
  role_label: string;
  online: boolean;
  last_seen: string | null;
  current_case_id: string | null;
  open_assigned: number;
  resolved_today: number;
};
export type AgentState = {
  auto_assign: boolean;
  briefs_drafted: number;
  liens_placed: number;
  cases_auto_assigned: number;
  cases_triaged: number;
};
export type Guidance = {
  references: {
    id: string;
    title: string;
    source_url: string;
    source_date: string;
    applicability: string;
    control: string;
    status: string;
    test_evidence: string[];
  }[];
  requirements?: {
    issuer: string;
    source: string;
    url: string | null;
    date: string;
    status: string;
    what_it_requires: string;
    how_fraudlens_models_it: string;
    not_covered: string;
  }[];
  disclaimer: string;
};
export class OperationsError extends Error {
  constructor(
    public status: number,
    message: string,
    public data: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "OperationsError";
  }
}
const article = (label: string) => (/^[AEIOUL]/.test(label) ? "an" : "a");
/** Turns role (403) and ownership (409) refusals into the console's copy. */
export function explainError(
  err: unknown,
  team: TeamMember[] = [],
  fallback = "Request failed.",
) {
  if (err instanceof OperationsError) {
    const role = err.data.required_role as Role | undefined;
    if (err.status === 403 && role && ROLE_LABEL[role])
      return `This needs ${article(ROLE_LABEL[role])} ${ROLE_LABEL[role]}. Request approval instead.`;
    const owner = err.data.assignee as string | undefined;
    if (err.status === 409 && owner) {
      const name =
        team.find((m) => m.username === owner)?.display_name ?? owner;
      return `${name} already claimed this case.`;
    }
    return err.message;
  }
  return err instanceof Error ? err.message : fallback;
}
export async function opsFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const token = getToken();
  if (!token)
    throw new OperationsError(401, "Your session has ended. Sign in again.");
  const response = await fetch(OPS_BASE + path, {
    ...init,
    cache: "no-store",
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
      Authorization: `Bearer ${token}`,
    },
  });
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    throw new OperationsError(
      response.status,
      typeof data?.detail === "string"
        ? data.detail
        : `Request failed (${response.status}).`,
      data && typeof data === "object" ? data : {},
    );
  }
  return response.json() as Promise<T>;
}
export function decideCase(
  caseId: string,
  action: Decision,
  version: number,
  notes: string,
) {
  if (
    (action === "confirm_fraud" || action === "false_positive") &&
    !notes.trim()
  )
    throw new OperationsError(
      422,
      "Add investigation notes before recording a verdict.",
    );
  return opsFetch<Case>(`/cases/${encodeURIComponent(caseId)}/decision`, {
    method: "POST",
    body: JSON.stringify({
      action,
      expected_version: version,
      notes: notes.trim(),
    }),
  });
}
const casePath = (caseId: string, suffix: string) =>
  `/cases/${encodeURIComponent(caseId)}/${suffix}`;
const post = <T,>(path: string, body: unknown) =>
  opsFetch<T>(path, { method: "POST", body: JSON.stringify(body) });
export function runCaseAction(
  caseId: string,
  action: CaseAction,
  version: number,
  notes: string,
  extra: { amount_minor?: number | null; target_account_id?: string | null } = {},
) {
  return post<Case>(casePath(caseId, "decision"), {
    action,
    expected_version: version,
    notes: notes.trim(),
    ...(extra.amount_minor ? { amount_minor: extra.amount_minor } : {}),
    ...(extra.target_account_id
      ? { target_account_id: extra.target_account_id }
      : {}),
  });
}
export const claimCase = (caseId: string, version: number) =>
  post<Case>(casePath(caseId, "claim"), { expected_version: version });
export const assignCase = (caseId: string, username: string, version: number) =>
  post<Case>(casePath(caseId, "assign"), {
    username,
    expected_version: version,
  });
export const requestApproval = (
  caseId: string,
  action: ApprovalAction,
  version: number,
  notes: string,
  targetAccountId?: string | null,
) =>
  post<Case>(casePath(caseId, "approval-request"), {
    action,
    expected_version: version,
    notes: notes.trim(),
    ...(targetAccountId ? { target_account_id: targetAccountId } : {}),
  });
export const decideApproval = (caseId: string, approve: boolean, notes = "") =>
  post<Case>(casePath(caseId, "approval"), { approve, notes: notes.trim() });
export const heartbeat = (currentCaseId: string | null) =>
  post<{ ok: true }>("/presence/heartbeat", { current_case_id: currentCaseId });
export const fileComplaint = (complaint: {
  complaint_id: string;
  source: "1930_helpline" | "ncrp_portal" | "branch";
  victim_account_id: string;
  reported_txn_id: string;
  reported_at: string;
}) => post<Case>("/complaints", complaint);
export const setAgentSettings = (autoAssign: boolean) =>
  post<{ auto_assign: boolean }>("/agent/settings", {
    auto_assign: autoAssign,
  });
export const getBrief = (caseId: string) =>
  opsFetch<Brief>(casePath(caseId, "brief"));
export async function exportReport(
  caseId: string,
  format: "json" | "markdown" | "pdf",
) {
  const token = getToken();
  if (!token)
    throw new OperationsError(401, "Sign in again to export a report.");
  const response = await fetch(
    `${OPS_BASE}/cases/${encodeURIComponent(caseId)}/report?format=${format}`,
    { headers: { Authorization: `Bearer ${token}` } },
  );
  if (!response.ok)
    throw new OperationsError(
      response.status,
      "Report export failed. Try again.",
    );
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `${caseId}.${format === "markdown" ? "md" : format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export const money = (minor: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  }).format(minor / 100);
/** Whole rupees without paise (₹48,000); paise shown only when present. */
export const rupees = (minor: number) =>
  new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: minor % 100 ? 2 : 0,
    maximumFractionDigits: 2,
  }).format(minor / 100);
export const dateTime = (iso: string) =>
  new Date(iso).toLocaleString("en-IN", {
    dateStyle: "medium",
    timeStyle: "medium",
    timeZone: "Asia/Kolkata",
  });
export const human = (value: string) => value.replaceAll("_", " ");
export function newestSnapshot(
  current: Snapshot | null,
  incoming: Snapshot,
): Snapshot {
  return current && current.cursor > incoming.cursor ? current : incoming;
}
