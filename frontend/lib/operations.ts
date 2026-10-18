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
  simulation_state: { running: boolean; interval_seconds: number };
  detection: { version: string; coverage: Record<string, unknown>[] };
};
export type Decision =
  "investigate" | "escalate" | "confirm_fraud" | "false_positive";
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
  disclaimer: string;
};
export class OperationsError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "OperationsError";
  }
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
